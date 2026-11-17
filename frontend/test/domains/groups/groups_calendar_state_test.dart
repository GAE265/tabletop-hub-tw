// 情境對應 openspec/changes/add-groups-calendar/specs/groups-calendar-page/spec.md
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/state/groups_calendar_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

Future<void> loaded(ProviderContainer container) =>
    container.read(groupsCalendarProvider.notifier).loaded;

void main() {
  group('月曆顯示每天的團數', () {
    test('載入當月：依台灣時間的月份邊界查詢，計算每天團數', () async {
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(id: 'a', startAt: taipei(11, 14, 13)),
          fakeGroup(id: 'b', startAt: taipei(11, 14, 19)),
          fakeGroup(id: 'c', startAt: taipei(11, 20)),
          fakeGroup(id: 'dec', startAt: taipei(12, 2)),
        ],
      );
      final container = makeContainer(repo);
      container.read(groupsCalendarProvider);
      await loaded(container);

      final state = container.read(groupsCalendarProvider);
      expect(state.month, DateTime(2026, 11));
      expect(state.selectedDate, DateTime(2026, 11, 14));
      expect(repo.listCalls.single.startFrom, taipei(11, 1, 0));
      expect(repo.listCalls.single.startBefore, taipei(12, 1, 0));
      expect(container.read(calendarCountsProvider), {
        DateTime(2026, 11, 14): 2,
        DateTime(2026, 11, 20): 1,
      });
    });

    test('跨日的時區換算：台灣時間 11/14 00:30 計入 11/14', () async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(startAt: DateTime.utc(2026, 11, 13, 16, 30))],
      );
      final container = makeContainer(repo);
      container.read(groupsCalendarProvider);
      await loaded(container);
      expect(container.read(calendarCountsProvider), {
        DateTime(2026, 11, 14): 1,
      });
    });

    test('切換到下個月與上個月，重新查詢', () async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(id: 'dec', startAt: taipei(12, 2))],
      );
      final container = makeContainer(repo);
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;

      notifier.nextMonth();
      await notifier.loaded;
      expect(container.read(groupsCalendarProvider).month, DateTime(2026, 12));
      expect(repo.listCalls.last.startFrom, taipei(12, 1, 0));
      expect(repo.listCalls.last.startBefore, DateTime.utc(2026, 12, 31, 16));
      expect(container.read(calendarCountsProvider), {
        DateTime(2026, 12, 2): 1,
      });

      notifier.previousMonth();
      await notifier.loaded;
      expect(container.read(groupsCalendarProvider).month, DateTime(2026, 11));
      expect(container.read(calendarCountsProvider), isEmpty);
    });

    test('切換使用者：重新查詢，保留月份與選取的日期', () async {
      // 後端依目前使用者回傳 my_status，換人後同一團的資料就不同
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(id: 'dec', startAt: taipei(12, 2), myStatus: 'member'),
        ],
      );
      final container = makeContainer(repo, userId: 'u-staff');
      // 畫面開著時一直在監聽月曆；沒人監聽的 provider 會暫停，收不到換人的通知
      container.listen(groupsCalendarProvider, (_, _) {});
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;
      notifier
        ..nextMonth()
        ..selectDate(DateTime(2026, 12, 2));
      await notifier.loaded;
      final callsBefore = repo.listCalls.length;

      repo.groups = [fakeGroup(id: 'dec', startAt: taipei(12, 2))];
      await switchUser(container, 'u-admin');
      await notifier.loaded;

      final state = container.read(groupsCalendarProvider);
      expect(repo.listCalls.length, callsBefore + 1);
      expect(repo.listCalls.last.startFrom, taipei(12, 1, 0));
      expect(state.month, DateTime(2026, 12));
      expect(state.selectedDate, DateTime(2026, 12, 2));
      expect(container.read(selectedDayGroupsProvider).single.myStatus, isNull);
    });

    test('今天：回到本月並選取今天', () async {
      final container = makeContainer(FakeGroupsRepository());
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;
      notifier
        ..nextMonth()
        ..selectDate(DateTime(2026, 12, 5));
      await notifier.loaded;

      notifier.goToToday();
      await notifier.loaded;
      final state = container.read(groupsCalendarProvider);
      expect(state.month, DateTime(2026, 11));
      expect(state.selectedDate, DateTime(2026, 11, 14));
    });

    test('載入中：不顯示舊月份的團數', () async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(startAt: taipei(11, 20))],
      );
      final container = makeContainer(repo);
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;
      expect(container.read(calendarCountsProvider), isNotEmpty);

      notifier.nextMonth();
      expect(container.read(groupsCalendarProvider).groups.isLoading, isTrue);
      expect(container.read(calendarCountsProvider), isEmpty);
      await notifier.loaded;
    });

    test('載入失敗：保留錯誤，重試後恢復', () async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(startAt: taipei(11, 20))],
      )..error = const ApiException(code: 'NETWORK_ERROR', message: '無法連線到伺服器');
      final container = makeContainer(repo);
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;
      final groups = container.read(groupsCalendarProvider).groups;
      expect(groups.hasError, isTrue);
      expect((groups.error! as ApiException).message, '無法連線到伺服器');

      repo.error = null;
      notifier.reload();
      await notifier.loaded;
      expect(container.read(calendarCountsProvider), {
        DateTime(2026, 11, 20): 1,
      });
    });

    test('一個月超過 100 團：繼續載入後面的分頁', () async {
      final repo = FakeGroupsRepository(
        groups: [
          for (var i = 0; i < 150; i++)
            fakeGroup(id: 'g$i', startAt: taipei(11, 1 + i % 28)),
        ],
      );
      final container = makeContainer(repo);
      container.read(groupsCalendarProvider);
      await loaded(container);
      expect(repo.listCalls.map((c) => (c.page, c.pageSize)), [
        (1, 100),
        (2, 100),
      ]);
      expect(
        container.read(groupsCalendarProvider).groups.value,
        hasLength(150),
      );
    });
  });

  group('當日揪團列表', () {
    test('選取日期：依開始時間排序', () async {
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(id: 'late', startAt: taipei(11, 14, 19)),
          fakeGroup(id: 'early', startAt: taipei(11, 14, 13)),
          fakeGroup(id: 'other', startAt: taipei(11, 20)),
        ],
      );
      final container = makeContainer(repo);
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;
      expect(container.read(selectedDayGroupsProvider).map((g) => g.id), [
        'early',
        'late',
      ]);

      notifier.selectDate(DateTime(2026, 11, 21));
      expect(container.read(selectedDayGroupsProvider), isEmpty);
    });

    test('名額狀態文字', () {
      final start = taipei(11, 20);
      expect(
        groupSlotLabel(fakeGroup(startAt: start, status: 'cancelled')),
        '已取消',
      );
      expect(groupSlotLabel(fakeGroup(startAt: start, status: 'ended')), '已結束');
      expect(
        groupSlotLabel(
          fakeGroup(
            startAt: start,
            capacity: 2,
            memberCount: 2,
            waitlistCount: 2,
          ),
        ),
        '已額滿，候補 2 人',
      );
      expect(
        groupSlotLabel(fakeGroup(startAt: start, capacity: 4, memberCount: 1)),
        '剩 3 位',
      );
    });
  });

  group('依開團主篩選', () {
    test('選項附場數；選擇後月曆與列表只算該開團主', () async {
      final repo = FakeGroupsRepository(
        groups: [
          for (var i = 0; i < 3; i++)
            fakeGroup(
              id: 'a$i',
              startAt: taipei(11, 14 + i),
              organizerId: 'u-a',
              organizerName: 'A',
            ),
          fakeGroup(
            id: 'b',
            startAt: taipei(11, 14, 13),
            organizerId: 'u-b',
            organizerName: 'B',
          ),
        ],
      );
      final container = makeContainer(repo);
      final notifier = container.read(groupsCalendarProvider.notifier);
      await notifier.loaded;

      final options = container.read(organizerOptionsProvider);
      expect(options.map((o) => (o.id, o.name, o.count)), [
        ('u-a', 'A', 3),
        ('u-b', 'B', 1),
      ]);

      notifier.setOrganizer('u-a');
      expect(container.read(calendarCountsProvider), {
        DateTime(2026, 11, 14): 1,
        DateTime(2026, 11, 15): 1,
        DateTime(2026, 11, 16): 1,
      });
      expect(container.read(selectedDayGroupsProvider).map((g) => g.id), [
        'a0',
      ]);

      notifier.setOrganizer(null);
      expect(container.read(calendarCountsProvider)[DateTime(2026, 11, 14)], 2);
    });
  });

  test('已知店家：從當月揪團整理出不重複的店家', () async {
    final repo = FakeGroupsRepository(
      groups: [
        fakeGroup(
          id: 'a',
          startAt: taipei(11, 14),
          shopId: 's1',
          shopName: '甲店',
        ),
        fakeGroup(
          id: 'b',
          startAt: taipei(11, 15),
          shopId: 's1',
          shopName: '甲店',
        ),
        fakeGroup(
          id: 'c',
          startAt: taipei(11, 16),
          shopId: 's2',
          shopName: '乙店',
        ),
      ],
    );
    final container = makeContainer(repo);
    container.read(groupsCalendarProvider);
    await loaded(container);
    expect(container.read(knownShopsProvider).map((s) => s.name), ['甲店', '乙店']);
  });
}
