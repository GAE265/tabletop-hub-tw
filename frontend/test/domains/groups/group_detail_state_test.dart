// 情境對應 openspec/changes/add-groups-calendar/specs/groups-calendar-page/spec.md
// 「報名、候補與退出」
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/state/group_detail_state.dart';
import 'package:tabletop_hub/domains/groups/state/groups_calendar_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

Future<GroupDetailNotifier> open(ProviderContainer container, String id) async {
  // 詳細資料是 autoDispose：畫面開著時一直有人監聽，測試也照做
  container.listen(groupDetailProvider(id), (_, _) {});
  final notifier = container.read(groupDetailProvider(id).notifier);
  await notifier.loaded;
  return notifier;
}

void main() {
  test('載入揪團與名單', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 20))],
    );
    repo.members['g-1'] = [
      GroupMember(
        userId: 'u-org',
        displayName: '開團主',
        status: 'member',
        joinedAt: DateTime.utc(2026, 11, 1),
      ),
    ];
    final container = makeContainer(repo);
    await open(container, 'g-1');
    final state = container.read(groupDetailProvider('g-1'));
    expect(state.group.value?.id, 'g-1');
    expect(state.members.single.displayName, '開團主');
  });

  test('揪團不存在：顯示錯誤', () async {
    final container = makeContainer(FakeGroupsRepository());
    await open(container, 'missing');
    final group = container.read(groupDetailProvider('missing')).group;
    expect(group.hasError, isTrue);
    expect((group.error! as ApiException).code, 'GROUP_NOT_FOUND');
  });

  group('依身分與狀態決定按鈕', () {
    final start = taipei(11, 20);
    Future<List<GroupAction>> actions(
      Group group, {
      String? userId = 'u-player',
    }) async {
      final container = makeContainer(
        FakeGroupsRepository(groups: [group]),
        userId: userId,
      );
      await open(container, group.id);
      return container.read(groupDetailProvider(group.id)).actionsFor(userId);
    }

    test('未報名、還有名額：報名', () async {
      expect(await actions(fakeGroup(startAt: start)), [GroupAction.join]);
    });

    test('未報名、額滿：加入候補', () async {
      expect(
        await actions(fakeGroup(startAt: start, capacity: 2, memberCount: 2)),
        [GroupAction.joinWaitlist],
      );
    });

    test('已是成員：退出、填入戰績；候補：只有退出', () async {
      expect(await actions(fakeGroup(startAt: start, myStatus: 'member')), [
        GroupAction.leave,
        GroupAction.recordMatch,
      ]);
      expect(await actions(fakeGroup(startAt: start, myStatus: 'waitlisted')), [
        GroupAction.leave,
      ]);
    });

    test('開團主：編輯、訂位、填入戰績、確定成團、取消揪團', () async {
      expect(
        await actions(
          fakeGroup(
            startAt: start,
            organizerId: 'u-player',
            myStatus: 'member',
          ),
        ),
        [
          GroupAction.edit,
          GroupAction.book,
          GroupAction.recordMatch,
          GroupAction.confirm,
          GroupAction.cancel,
        ],
      );
    });

    test('已成團：開團主沒有「確定成團」', () async {
      expect(
        await actions(
          fakeGroup(
            startAt: start,
            organizerId: 'u-player',
            myStatus: 'member',
            confirmedAt: nowUtc,
          ),
        ),
        [
          GroupAction.edit,
          GroupAction.book,
          GroupAction.recordMatch,
          GroupAction.cancel,
        ],
      );
    });

    test('已取消或已結束：沒有按鈕', () async {
      expect(
        await actions(fakeGroup(startAt: start, status: 'cancelled')),
        isEmpty,
      );
      expect(
        await actions(fakeGroup(startAt: start, status: 'ended')),
        isEmpty,
      );
    });

    test('已結束：開團主與成員只有填入戰績，候補沒有按鈕', () async {
      expect(
        await actions(
          fakeGroup(
            startAt: start,
            status: 'ended',
            organizerId: 'u-player',
            myStatus: 'member',
          ),
        ),
        [GroupAction.recordMatch],
      );
      expect(
        await actions(
          fakeGroup(startAt: start, status: 'ended', myStatus: 'member'),
        ),
        [GroupAction.recordMatch],
      );
      expect(
        await actions(
          fakeGroup(startAt: start, status: 'ended', myStatus: 'waitlisted'),
        ),
        isEmpty,
      );
    });

    test('已取消：開團主與成員都沒有按鈕', () async {
      expect(
        await actions(
          fakeGroup(
            startAt: start,
            status: 'cancelled',
            organizerId: 'u-player',
            myStatus: 'member',
          ),
        ),
        isEmpty,
      );
    });

    test('切換使用者：重新載入，按鈕依新身分決定', () async {
      // 店家人員已報名，額滿；換成管理員後，後端回傳的 my_status 是空的
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(
            startAt: start,
            capacity: 2,
            memberCount: 2,
            myStatus: 'member',
          ),
        ],
      );
      final container = makeContainer(repo, userId: 'u-staff');
      final notifier = await open(container, 'g-1');
      // 成員也有「填入戰績」
      expect(container.read(groupDetailProvider('g-1')).actionsFor('u-staff'), [
        GroupAction.leave,
        GroupAction.recordMatch,
      ]);

      repo.groups = [fakeGroup(startAt: start, capacity: 2, memberCount: 2)];
      await switchUser(container, 'u-admin');
      await notifier.loaded;

      expect(container.read(groupDetailProvider('g-1')).actionsFor('u-admin'), [
        GroupAction.joinWaitlist,
      ]);
    });
  });

  test('報名成功：顯示訊息、重新載入揪團與月曆', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 20))],
    );
    final container = makeContainer(repo);
    final calendar = container.read(groupsCalendarProvider.notifier);
    await calendar.loaded;
    final listCallsBefore = repo.listCalls.length;
    final notifier = await open(container, 'g-1');

    await notifier.join();
    final state = container.read(groupDetailProvider('g-1'));
    expect(repo.joinCalls, ['g-1']);
    expect(state.message, '報名成功');
    expect(state.error, isNull);
    expect(state.group.value?.remainingSlots, 2);
    // 報名成為成員後也可以填入戰績
    expect(state.actionsFor('u-player'), [
      GroupAction.leave,
      GroupAction.recordMatch,
    ]);
    await calendar.loaded;
    expect(repo.listCalls.length, greaterThan(listCallsBefore));
  });

  test('額滿加入候補：顯示順位', () async {
    final repo =
        FakeGroupsRepository(
            groups: [
              fakeGroup(startAt: taipei(11, 20), capacity: 2, memberCount: 2),
            ],
          )
          ..joinResult = const JoinResult(
            userId: 'u-player',
            status: 'waitlisted',
            waitlistPosition: 2,
          );
    final container = makeContainer(repo);
    final notifier = await open(container, 'g-1');
    await notifier.join();
    expect(container.read(groupDetailProvider('g-1')).message, '已加入候補，目前第 2 位');
  });

  test('退出：以目前使用者的 id 呼叫退出 API', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 20), myStatus: 'member')],
    );
    final container = makeContainer(repo);
    final notifier = await open(container, 'g-1');
    await notifier.leave();
    expect(repo.removeCalls, [('g-1', 'u-player')]);
    final state = container.read(groupDetailProvider('g-1'));
    expect(state.message, '已退出揪團');
    expect(state.actionsFor('u-player'), [GroupAction.join]);
  });

  test('取消揪團：送出 status=cancelled', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 20), organizerId: 'u-player')],
    );
    final container = makeContainer(repo);
    final notifier = await open(container, 'g-1');
    await notifier.cancel();
    final (id, changes) = repo.updateCalls.single;
    expect(id, 'g-1');
    expect(changes, {'status': 'cancelled'});
    final state = container.read(groupDetailProvider('g-1'));
    expect(state.message, '已取消揪團');
    expect(state.group.value?.status, 'cancelled');
  });

  test('操作失敗：顯示後端訊息，按鈕恢復可按', () async {
    final repo =
        FakeGroupsRepository(groups: [fakeGroup(startAt: taipei(11, 20))])
          ..actionError = const ApiException(
            code: 'GROUP_CLOSED',
            message: '揪團已取消或已結束',
            statusCode: 409,
          );
    final container = makeContainer(repo);
    final notifier = await open(container, 'g-1');
    await notifier.join();
    final state = container.read(groupDetailProvider('g-1'));
    expect(state.error, '揪團已取消或已結束');
    expect(state.message, isNull);
    expect(state.busy, isFalse);
  });

  test('操作進行中：按鈕停用，重複按不會重複送出', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 20))],
    )..actionGate = Completer<void>();
    final container = makeContainer(repo);
    final notifier = await open(container, 'g-1');

    final first = notifier.join();
    expect(container.read(groupDetailProvider('g-1')).busy, isTrue);
    await notifier.join();
    expect(repo.joinCalls, hasLength(1));

    repo.actionGate!.complete();
    await first;
    expect(container.read(groupDetailProvider('g-1')).busy, isFalse);
  });
}
