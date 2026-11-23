// 正式揪團詳細頁（spec：groups-calendar-page 的「報名、候補與退出」）。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/pages/group_detail_page.dart';
import 'package:tabletop_hub/domains/groups/state/current_user.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

FakeGroupsRepository repoWith({
  int memberCount = 1,
  int waitlistCount = 0,
  String status = 'open',
  String? myStatus,
}) => FakeGroupsRepository(
  groups: [
    fakeGroup(
      id: 'g-1',
      title: '週末輕策略',
      startAt: taipei(11, 14, 19),
      memberCount: memberCount,
      waitlistCount: waitlistCount,
      status: status,
      myStatus: myStatus,
      fee: 150,
    ),
  ],
);

Finder button(String label) =>
    find.ancestor(of: find.text(label), matching: find.byType(FilledButton));

/// [box] 的外框底邊比上邊粗，而且有陰影（有厚度）。
void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

void main() {
  // Stitch 版面（和揪團月曆同一套樣式）：木紋背景，文字放在卡片上，按鈕有厚度、按得下去
  group('Stitch 版面', () {
    testWidgets('木紋背景；資訊卡與名單卡有厚度', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('group-detail-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      for (final key in ['group-info', 'group-members']) {
        final card = find.byKey(Key(key));
        expectThick(
          tester,
          find.descendant(of: card, matching: find.byType(DecoratedBox)).first,
          key,
        );
      }
      expect(
        find.descendant(
          of: find.byKey(const Key('group-members')),
          matching: find.textContaining('名單（'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('「報名」有厚度，按住往下沉，移開後彈回', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
      );
      final join = button('報名');
      final frame = find
          .ancestor(of: join, matching: find.byType(DecoratedBox))
          .first;
      double edge() =>
          ((tester.widget<DecoratedBox>(frame).decoration as BoxDecoration)
                      .border!
                  as Border)
              .bottom
              .width;
      expectThick(tester, frame);
      final restEdge = edge();
      final restTop = tester.getTopLeft(join).dy;
      final gesture = await tester.startGesture(tester.getCenter(join));
      await tester.pumpAndSettle();
      expect(edge(), lessThan(restEdge));
      expect(tester.getTopLeft(join).dy, greaterThan(restTop));
      await gesture.cancel();
      await tester.pumpAndSettle();
      expect(edge(), restEdge);
      expect(tester.getTopLeft(join).dy, restTop);
    });

    Finder inKey(String key, Finder f) =>
        find.descendant(of: find.byKey(Key(key)), matching: f);

    GroupMember member(
      String id,
      String name, {
      String status = 'member',
      int? position,
    }) => GroupMember(
      userId: id,
      displayName: name,
      status: status,
      waitlistPosition: position,
      joinedAt: nowUtc,
    );

    testWidgets('資訊卡：時數、分項小標（聚會時間、桌遊店家、費用）', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
      );
      for (final text in ['2 小時', '聚會時間', '桌遊店家', '費用']) {
        expect(
          inKey('group-info', find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
    });

    testWidgets('開團主卡片；有簡介時另一張「揪團說明」卡', (tester) async {
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(
            id: 'g-1',
            startAt: taipei(11, 14, 19),
            organizerName: '阿瑋',
            description: '新手友善，現場教學',
          ),
        ],
      );
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repo,
      );
      expect(inKey('group-organizer', find.text('開團主：阿瑋')), findsOneWidget);
      expect(inKey('group-description', find.text('揪團說明')), findsOneWidget);
      expect(
        inKey('group-description', find.text('新手友善，現場教學')),
        findsOneWidget,
      );
    });

    testWidgets('沒有簡介：不顯示「揪團說明」卡', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
      );
      expect(find.byKey(const Key('group-description')), findsNothing);
    });

    testWidgets('名單：成員與候補分開，自己標「我」，有空位時顯示剩幾個', (tester) async {
      final repo =
          FakeGroupsRepository(
              groups: [
                fakeGroup(
                  id: 'g-1',
                  startAt: taipei(11, 14, 19),
                  capacity: 4,
                  memberCount: 2,
                  waitlistCount: 1,
                  organizerId: 'u-org',
                  organizerName: '阿瑋',
                  myStatus: 'member',
                ),
              ],
            )
            ..members['g-1'] = [
              member('u-org', '阿瑋'),
              member('u-player', '小安'),
              member('u-w', '阿翔', status: 'waitlisted', position: 1),
            ];
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repo,
      );
      Finder members(Finder f) => inKey('group-members', f);
      expect(members(find.text('名單（2 人）')), findsOneWidget);
      expect(members(find.text('我')), findsOneWidget);
      expect(members(find.text('尚有 2 個空位')), findsOneWidget);
      expect(members(find.text('候補（1 人等待中）')), findsOneWidget);
      expect(members(find.text('候補第 1 位')), findsOneWidget);
      // 「我」標在自己那一列
      final me = find
          .ancestor(of: members(find.text('小安')), matching: find.byType(Row))
          .first;
      expect(find.descendant(of: me, matching: find.text('我')), findsOneWidget);
    });

    testWidgets('額滿：不顯示空位提示', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(memberCount: 4),
      );
      expect(find.textContaining('個空位'), findsNothing);
    });

    testWidgets('操作台：顯示我的身分，操作按鈕放在操作台裡', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(myStatus: 'member'),
      );
      expect(inKey('group-role', find.text('成員')), findsOneWidget);
      expect(inKey('group-actions', find.text('退出')), findsOneWidget);
      expect(inKey('group-actions', find.text('填入戰績')), findsOneWidget);
    });

    testWidgets('操作台：一般操作在「揪團動作」，退出與取消在「退出與取消」並標身分', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(myStatus: 'member'),
      );
      Finder section(String key) => find.byKey(Key(key));
      expect(
        find.descendant(
          of: section('group-actions-main'),
          matching: find.text('填入戰績'),
        ),
        findsOneWidget,
      );
      final danger = section('group-actions-danger');
      expect(
        find.descendant(of: danger, matching: find.text('退出')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: danger, matching: find.text('退出這場揪團')),
        findsOneWidget,
      );
    });

    testWidgets('未報名：沒有操作台，報名在底部固定列', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
      );
      expect(find.byKey(const Key('group-actions')), findsNothing);
      final bar = find.byKey(const Key('group-join-bar'));
      expect(
        find.descendant(of: bar, matching: find.text('每人 \$150')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: bar, matching: find.text('剩 3 席')),
        findsOneWidget,
      );
      expect(find.descendant(of: bar, matching: button('報名')), findsOneWidget);
      // 固定在畫面底部：捲動內容不會帶著它跑
      final top = tester.getTopLeft(bar).dy;
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -500));
      await tester.pumpAndSettle();
      expect(tester.getTopLeft(bar).dy, top);
    });

    testWidgets('額滿：底部固定列是「加入候補」與「已額滿」', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(memberCount: 4),
      );
      final bar = find.byKey(const Key('group-join-bar'));
      expect(
        find.descendant(of: bar, matching: find.text('已額滿')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: bar, matching: button('加入候補')),
        findsOneWidget,
      );
    });

    testWidgets('已報名：沒有底部報名列', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(myStatus: 'member'),
      );
      expect(find.byKey(const Key('group-join-bar')), findsNothing);
    });

    testWidgets('手機底部被導覽列蓋住：捲到最底時名單停在導覽列上方', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repoWith(),
        size: const Size(400, 600),
        bottomInset: 120,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(
        tester.getBottomLeft(find.byKey(const Key('group-members'))).dy,
        lessThanOrEqualTo(600 - 120),
      );
    });
  });

  testWidgets('顯示揪團資訊', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(),
    );
    expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    expect(find.text('週末輕策略'), findsWidgets);
    expect(find.text('測試桌遊店'), findsOneWidget);
    expect(find.text('開團主：開團主'), findsOneWidget);
    expect(find.text('\$150／人'), findsOneWidget);
    expect(find.text('剩 3 位'), findsOneWidget);
  });

  testWidgets('報名成功：顯示「報名成功」，按鈕變成「退出」', (tester) async {
    final repo = repoWith();
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pumpAndSettle();
    expect(repo.joinCalls, ['g-1']);
    expect(find.text('報名成功'), findsOneWidget);
    expect(button('退出'), findsOneWidget);
  });

  testWidgets('額滿：按「加入候補」，顯示候補順位', (tester) async {
    final repo = repoWith(memberCount: 4, waitlistCount: 1)
      ..joinResult = const JoinResult(
        userId: 'u-player',
        status: 'waitlisted',
        waitlistPosition: 2,
      );
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('加入候補'));
    await tester.pumpAndSettle();
    expect(find.text('已加入候補，目前第 2 位'), findsOneWidget);
    expect(button('退出'), findsOneWidget);
  });

  testWidgets('退出：確認後呼叫 API，按鈕變回「報名」', (tester) async {
    final repo = repoWith(memberCount: 2, myStatus: 'member');
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('退出'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('確定'));
    await tester.pumpAndSettle();
    expect(repo.removeCalls, [('g-1', 'u-player')]);
    expect(button('報名'), findsOneWidget);
  });

  testWidgets('操作失敗：顯示後端訊息，按鈕恢復可按', (tester) async {
    final repo = repoWith()
      ..actionError = const ApiException(
        code: 'GROUP_CLOSED',
        message: '這個揪團已經結束或取消',
        statusCode: 409,
      );
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pumpAndSettle();
    expect(find.text('這個揪團已經結束或取消'), findsOneWidget);
    expect(tester.widget<FilledButton>(button('報名')).onPressed, isNotNull);
  });

  testWidgets('操作進行中：按鈕停用，不能重複送出', (tester) async {
    final repo = repoWith()..actionGate = Completer<void>();
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.widget<FilledButton>(button('報名')).onPressed, isNull);
    await tester.tap(button('報名'), warnIfMissed: false);
    expect(repo.joinCalls, ['g-1']);

    repo.actionGate!.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('開團主只看到「編輯」與「取消揪團」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
      userId: 'u-org',
    );
    expect(find.text('編輯'), findsOneWidget);
    expect(find.text('取消揪團'), findsOneWidget);
    expect(find.text('報名'), findsNothing);
    expect(find.text('退出'), findsNothing);
  });

  testWidgets('開團主取消揪團：確認後送出 cancelled', (tester) async {
    final repo = repoWith(myStatus: 'member');
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
      userId: 'u-org',
    );
    // 團務操作改成列表後，「取消揪團」在畫面下方，先捲過去
    await tester.ensureVisible(find.text('取消揪團'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('取消揪團'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('確定'));
    await tester.pumpAndSettle();
    final (id, changes) = repo.updateCalls.single;
    expect(id, 'g-1');
    expect(changes, {'status': 'cancelled'});
    expect(find.text('已取消'), findsOneWidget);
  });

  testWidgets('已結束：顯示「已結束」，沒有報名按鈕', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(status: 'ended'),
    );
    expect(find.text('已結束'), findsOneWidget);
    expect(find.text('報名'), findsNothing);
  });

  testWidgets('載入失敗：顯示錯誤與「重試」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-missing'),
      repo: repoWith(),
    );
    expect(find.text('找不到這個揪團'), findsOneWidget);
    expect(find.text('重試'), findsOneWidget);
  });

  testWidgets('詳細頁顯示揪團的多款遊戲', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [
        fakeGroup(
          id: 'g-1',
          startAt: taipei(11, 14, 19),
          games: const [
            GameRef(id: 1, name: '阿瓦隆'),
            GameRef(id: 3, name: '馬可波羅'),
          ],
        ),
      ],
    );
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    expect(find.text('阿瓦隆'), findsOneWidget);
    expect(find.text('馬可波羅'), findsOneWidget);
  });

  testWidgets('開團主看到「訂位」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
      userId: 'u-org',
    );
    expect(find.text('訂位'), findsOneWidget);
  });

  testWidgets('一般成員看不到「訂位」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
    );
    expect(find.text('訂位'), findsNothing);
  });

  testWidgets('未報名的玩家看不到「訂位」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(),
    );
    expect(find.text('訂位'), findsNothing);
  });

  testWidgets('已取消的揪團：開團主看不到「訂位」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(status: 'cancelled', myStatus: 'member'),
      userId: 'u-org',
    );
    expect(find.text('訂位'), findsNothing);
  });

  testWidgets('開團主按「訂位」：跳到帶好揪團資料的訂位頁', (tester) async {
    Uri? opened;
    setScreenSize(tester, const Size(400, 900));
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const GroupDetailPage(groupId: 'g-1'),
        ),
        GoRoute(
          path: '/booking',
          builder: (context, state) {
            opened = state.uri;
            return const Text('訂位頁');
          },
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          groupsRepositoryProvider.overrideWithValue(
            repoWith(myStatus: 'member'),
          ),
          groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
          currentUserIdProvider.overrideWithValue('u-org'),
        ],
        child: MaterialApp.router(
          theme: buildAppTheme(const FakeAppFonts()),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('訂位'));
    await tester.pumpAndSettle();

    expect(find.text('訂位頁'), findsOneWidget);
    expect(opened!.queryParameters, {
      'shop_id': 's-shop',
      'date': '2026-11-14',
      'start': '19:00',
      'end': '21:00',
      'party_size': '4',
      'requests': '揪團：週末輕策略',
    });
  });

  testWidgets('開團主看到「填入戰績」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
      userId: 'u-org',
    );
    expect(find.text('填入戰績'), findsOneWidget);
  });

  testWidgets('成員看到「填入戰績」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
    );
    expect(find.text('填入戰績'), findsOneWidget);
    expect(find.text('退出'), findsOneWidget);
  });

  testWidgets('候補看不到「填入戰績」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'waitlisted'),
    );
    expect(find.text('填入戰績'), findsNothing);
  });

  testWidgets('已結束：成員只看到「填入戰績」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(status: 'ended', myStatus: 'member'),
    );
    expect(find.text('填入戰績'), findsOneWidget);
    expect(find.text('退出'), findsNothing);
  });

  testWidgets('按「填入戰績」：跳到只帶 group_id 的戰績頁', (tester) async {
    Uri? opened;
    setScreenSize(tester, const Size(400, 900));
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const GroupDetailPage(groupId: 'g-1'),
        ),
        GoRoute(
          path: '/matches',
          builder: (context, state) {
            opened = state.uri;
            return const Text('戰績頁');
          },
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          groupsRepositoryProvider.overrideWithValue(
            repoWith(myStatus: 'member'),
          ),
          groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
          currentUserIdProvider.overrideWithValue('u-player'),
        ],
        child: MaterialApp.router(
          theme: buildAppTheme(const FakeAppFonts()),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('填入戰績'));
    await tester.pumpAndSettle();

    expect(find.text('戰績頁'), findsOneWidget);
    expect(opened!.queryParameters, {'group_id': 'g-1'});
  });

  group('確定成團', () {
    /// 停用、文字是「已成團」的按鈕。
    bool isDisabledConfirmed(WidgetTester tester) {
      final finder = find.byKey(const Key('group-confirmed'));
      if (finder.evaluate().length != 1) return false;
      final button = tester.widget<ButtonStyleButton>(finder);
      return button.onPressed == null &&
          find
              .descendant(of: finder, matching: find.text('已成團'))
              .evaluate()
              .isNotEmpty;
    }

    Future<FakeGroupsRepository> pumpAs(
      WidgetTester tester, {
      String userId = 'u-org',
      String status = 'open',
      String? myStatus = 'member',
      DateTime? confirmedAt,
    }) async {
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(
            id: 'g-1',
            startAt: taipei(11, 14, 19),
            status: status,
            myStatus: myStatus,
            confirmedAt: confirmedAt,
          ),
        ],
      );
      await pumpGroupsWidget(
        tester,
        const GroupDetailPage(groupId: 'g-1'),
        repo: repo,
        userId: userId,
      );
      return repo;
    }

    testWidgets('開團主看到「確定成團」', (tester) async {
      await pumpAs(tester);
      expect(find.byKey(const Key('group-confirm')), findsOneWidget);
      expect(find.text('已成團'), findsNothing);
    });

    testWidgets('成員、候補、其他玩家看不到', (tester) async {
      for (final myStatus in ['member', 'waitlisted', null]) {
        await pumpAs(tester, userId: 'u-player', myStatus: myStatus);
        expect(find.byKey(const Key('group-confirm')), findsNothing);
      }
    });

    testWidgets('已成團：開團主的按鈕變成停用的「已成團」', (tester) async {
      await pumpAs(tester, confirmedAt: nowUtc);
      expect(find.byKey(const Key('group-confirm')), findsNothing);
      expect(isDisabledConfirmed(tester), isTrue);
    });

    testWidgets('已成團：成員與未報名的人也看到停用的「已成團」', (tester) async {
      for (final myStatus in ['member', null]) {
        await pumpAs(
          tester,
          userId: 'u-player',
          myStatus: myStatus,
          confirmedAt: nowUtc,
        );
        expect(isDisabledConfirmed(tester), isTrue);
      }
    });

    testWidgets('已取消、已結束：沒有「確定成團」也沒有「已成團」', (tester) async {
      for (final status in ['cancelled', 'ended']) {
        await pumpAs(tester, status: status, confirmedAt: nowUtc);
        expect(find.byKey(const Key('group-confirm')), findsNothing);
        expect(find.byKey(const Key('group-confirmed')), findsNothing);
      }
    });

    testWidgets('確認後送出 confirmed，按鈕變成停用的「已成團」', (tester) async {
      final repo = await pumpAs(tester);
      await tester.tap(find.byKey(const Key('group-confirm')));
      await tester.pumpAndSettle();
      expect(find.textContaining('通知所有成員'), findsOneWidget);
      await tester.tap(find.text('確定'));
      await tester.pumpAndSettle();
      expect(repo.updateCalls.single.$1, 'g-1');
      expect(repo.updateCalls.single.$2, {'confirmed': true});
      expect(find.byKey(const Key('group-confirm')), findsNothing);
      expect(isDisabledConfirmed(tester), isTrue);
    });

    testWidgets('對話框按取消：不送出', (tester) async {
      final repo = await pumpAs(tester);
      await tester.tap(find.byKey(const Key('group-confirm')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(repo.updateCalls, isEmpty);
    });

    testWidgets('失敗：顯示中文錯誤，按鈕保留', (tester) async {
      final repo = await pumpAs(tester);
      repo.actionError = const ApiException(
        code: 'GROUP_ALREADY_CONFIRMED',
        message: '這個揪團已經確定成團',
        statusCode: 409,
      );
      await tester.tap(find.byKey(const Key('group-confirm')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('確定'));
      await tester.pumpAndSettle();
      expect(find.text('這個揪團已經確定成團'), findsOneWidget);
      expect(find.byKey(const Key('group-confirm')), findsOneWidget);
    });

    testWidgets('成團後取消：顯示「已取消」，不顯示「已成團」', (tester) async {
      await pumpAs(tester, status: 'cancelled', confirmedAt: nowUtc);
      expect(find.text('已取消'), findsOneWidget);
      expect(find.text('已成團'), findsNothing);
    });
  });
}
