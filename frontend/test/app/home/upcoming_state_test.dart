// 首頁「接下來的行程」（spec：home-page 的「接下來的行程」）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/home/state/upcoming_state.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../domains/groups/support.dart';
import '../../support/fakes.dart';
import 'support.dart';

class TestUser extends Notifier<DevUser?> {
  TestUser(this.initial);

  final DevUser? initial;

  @override
  DevUser? build() => initial;

  void set(DevUser? user) => state = user;
}

final testUserProvider = NotifierProvider<TestUser, DevUser?>(
  () => TestUser(null),
);

ProviderContainer makeContainer({
  FakeBookingRepository? bookings,
  FakeGroupsRepository? groups,
  DevUser? user = homePlayer,
}) {
  final container = ProviderContainer(
    overrides: [
      bookingRepositoryProvider.overrideWithValue(
        bookings ?? FakeBookingRepository(),
      ),
      groupsRepositoryProvider.overrideWithValue(
        groups ?? FakeGroupsRepository(),
      ),
      groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
      testUserProvider.overrideWith(() => TestUser(user)),
      currentDevUserProvider.overrideWith((ref) => ref.watch(testUserProvider)),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

Future<List<UpcomingItem>> load(ProviderContainer container) {
  container.listen(upcomingProvider, (_, _) {});
  return container.read(upcomingProvider.future);
}

String describe(UpcomingItem item) => switch (item) {
  UpcomingBooking(:final booking) => 'booking ${booking.id}',
  UpcomingGroup(:final group) => 'group ${group.id}',
};

void main() {
  final clock = FixedOffsetClock(nowUtc);

  test('訂位與揪團合併，依開始時間由近到遠排序', () async {
    final bookings = FakeBookingRepository(
      mine: [
        homeBooking(id: 1, startAt: taipei(11, 23, 14)),
        homeBooking(id: 2, startAt: taipei(11, 21, 19)),
      ],
    );
    final groups = FakeGroupsRepository(
      groups: [
        fakeGroup(id: 'g-1', startAt: taipei(11, 22, 19), myStatus: 'member'),
      ],
    );
    final items = await load(makeContainer(bookings: bookings, groups: groups));
    expect(items.map(describe), ['booking 2', 'group g-1', 'booking 1']);
  });

  test('只列即將到來的：已取消、已完成、已開始的訂位，與沒報名、已開始的揪團都不列', () async {
    final bookings = FakeBookingRepository(
      mine: [
        homeBooking(id: 1, startAt: taipei(11, 21), status: 'cancelled'),
        homeBooking(id: 2, startAt: taipei(11, 21), status: 'completed'),
        homeBooking(id: 3, startAt: taipei(11, 14, 10)),
        homeBooking(id: 4, startAt: taipei(11, 21)),
      ],
    );
    final groups = FakeGroupsRepository(
      groups: [
        fakeGroup(id: 'g-none', startAt: taipei(11, 22)),
        fakeGroup(
          id: 'g-cancelled',
          startAt: taipei(11, 22),
          status: 'cancelled',
          myStatus: 'member',
        ),
        fakeGroup(id: 'g-past', startAt: taipei(11, 14, 9), myStatus: 'member'),
        fakeGroup(
          id: 'g-wait',
          startAt: taipei(11, 23),
          myStatus: 'waitlisted',
        ),
      ],
    );
    final items = await load(makeContainer(bookings: bookings, groups: groups));
    expect(items.map(describe), ['booking 4', 'group g-wait']);
  });

  test('查詢條件：訂位只查已確認、從台灣今天開始；揪團從現在開始、一次取 100 筆', () async {
    final bookings = FakeBookingRepository();
    final groups = FakeGroupsRepository();
    await load(makeContainer(bookings: bookings, groups: groups));
    expect(bookings.mineCalls.single.status, 'confirmed');
    expect(bookings.mineCalls.single.fromDate, '2026-11-14');
    expect(groups.listCalls.single.startFrom, nowUtc);
    expect(groups.listCalls.single.pageSize, 100);
  });

  test('最多 5 筆，取時間最近的', () async {
    final bookings = FakeBookingRepository(
      mine: [
        for (var day = 15; day <= 18; day++)
          homeBooking(id: day, startAt: taipei(11, day)),
      ],
    );
    final groups = FakeGroupsRepository(
      groups: [
        for (var day = 19; day <= 21; day++)
          fakeGroup(id: 'g-$day', startAt: taipei(11, day), myStatus: 'member'),
      ],
    );
    final items = await load(makeContainer(bookings: bookings, groups: groups));
    expect(items.map(describe), [
      'booking 15',
      'booking 16',
      'booking 17',
      'booking 18',
      'group g-19',
    ]);
  });

  test('訂位顯示店家名稱；對不到店家時沒有名稱', () async {
    final bookings = FakeBookingRepository(
      mine: [
        homeBooking(id: 1, startAt: taipei(11, 21), shopId: 's-b'),
        homeBooking(id: 2, startAt: taipei(11, 22), shopId: 's-unknown'),
      ],
    );
    final items = await load(makeContainer(bookings: bookings));
    expect((items[0] as UpcomingBooking).shopName, '乙店');
    expect((items[1] as UpcomingBooking).shopName, isNull);
  });

  test('店家人員查我的訂位回 403：不算錯誤，只列揪團', () async {
    final bookings = FakeBookingRepository(
      mine: [homeBooking(id: 1, startAt: taipei(11, 21))],
    )..mineError = forbidden;
    final groups = FakeGroupsRepository(
      groups: [
        fakeGroup(id: 'g-1', startAt: taipei(11, 22), myStatus: 'member'),
      ],
    );
    final items = await load(
      makeContainer(bookings: bookings, groups: groups, user: homeStaff),
    );
    expect(items.map(describe), ['group g-1']);
  });

  test('其他錯誤：進入錯誤狀態；重新載入成功後顯示行程', () async {
    final bookings = FakeBookingRepository(
      mine: [homeBooking(id: 1, startAt: taipei(11, 21))],
    )..mineError = networkError;
    final container = makeContainer(bookings: bookings);
    container.listen(upcomingProvider, (_, _) {});
    await expectLater(
      container.read(upcomingProvider.future),
      throwsA(isA<ApiException>()),
    );
    expect(container.read(upcomingProvider).hasError, isTrue);

    bookings.mineError = null;
    container.invalidate(upcomingProvider);
    final items = await container.read(upcomingProvider.future);
    expect(items.map(describe), ['booking 1']);
  });

  test('揪團 API 失敗也進入錯誤狀態', () async {
    final groups = FakeGroupsRepository()..error = networkError;
    final container = makeContainer(groups: groups);
    container.listen(upcomingProvider, (_, _) {});
    await expectLater(
      container.read(upcomingProvider.future),
      throwsA(isA<ApiException>()),
    );
  });

  test('切換身分：重新載入', () async {
    final bookings = FakeBookingRepository();
    final container = makeContainer(bookings: bookings);
    await load(container);
    expect(bookings.mineCalls, hasLength(1));

    container.read(testUserProvider.notifier).set(homeAdmin);
    await container.read(upcomingProvider.future);
    expect(bookings.mineCalls, hasLength(2));
  });

  // Stitch 版面：店家或揪團名稱當標題，下面是時間與人數，最下面是代碼或名額
  group('每一張卡片的文字', () {
    test('訂位：店家當標題、桌號、時間、人數、訂位代碼', () {
      final item = UpcomingBooking(
        homeBooking(id: 1, startAt: taipei(11, 21, 19), partySize: 4),
        shopName: '乙店',
      );
      final card = upcomingCard(clock, item);
      expect(card.kind, '訂位');
      expect(card.title, '乙店');
      expect(card.subtitle, '桌號 T1、T2');
      expect(card.when, '11/21（六）19:00–21:00');
      expect(card.people, '4 人');
      expect(card.footer, '訂位代碼 BK1');
      expect(card.action, '查看我的訂位');
      expect(upcomingStatus(item).label, '已確認');
      expect(upcomingRoute(item), '/booking/mine');
    });

    test('訂位：對不到店家時標題是「訂位」，沒有桌號時不顯示桌號', () {
      final card = upcomingCard(
        clock,
        UpcomingBooking(
          homeBooking(id: 1, startAt: taipei(11, 21), tableCodes: const []),
        ),
      );
      expect(card.title, '訂位');
      expect(card.subtitle, '');
    });

    test('揪團：名稱當標題、開團主與店家、時間、已報名人數、剩餘名額', () {
      final item = UpcomingGroup(
        fakeGroup(
          title: '阿瓦隆之夜',
          startAt: taipei(11, 22, 19),
          capacity: 7,
          memberCount: 5,
          organizerName: '小明',
          myStatus: 'member',
        ),
      );
      final card = upcomingCard(clock, item);
      expect(card.kind, '揪團');
      expect(card.title, '阿瓦隆之夜');
      expect(card.subtitle, '開團主：小明・測試桌遊店');
      expect(card.when, '11/22（日）19:00–21:00');
      expect(card.people, '5 / 7 人');
      expect(card.footer, '還有 2 個名額');
      expect(card.action, '查看揪團');
      expect(upcomingRoute(item), '/groups/g-1');
    });

    test('揪團額滿：底部顯示候補人數（「已額滿」在狀態標籤上，不重複）', () {
      String footer({int waitlist = 0}) => upcomingCard(
        clock,
        UpcomingGroup(
          fakeGroup(
            startAt: taipei(11, 22),
            capacity: 4,
            memberCount: 4,
            waitlistCount: waitlist,
            myStatus: 'member',
          ),
        ),
      ).footer;
      expect(footer(), '目前沒有候補');
      expect(footer(waitlist: 3), '候補 3 人');
    });

    test('揪團狀態：有名額是招募中、額滿是已額滿、我是候補是候補中', () {
      UpcomingStatus status({required int members, String my = 'member'}) =>
          upcomingStatus(
            UpcomingGroup(
              fakeGroup(
                startAt: taipei(11, 22),
                capacity: 4,
                memberCount: members,
                myStatus: my,
              ),
            ),
          );
      expect(status(members: 3).label, '招募中');
      expect(status(members: 4).label, '已額滿');
      expect(status(members: 4, my: 'waitlisted').label, '候補中');
    });

    test('時間用台灣時間', () {
      final card = upcomingCard(
        clock,
        UpcomingGroup(
          // 台灣 11/22 00:30＝UTC 11/21 16:30
          fakeGroup(startAt: taipei(11, 22, 0, 30), myStatus: 'member'),
        ),
      );
      expect(card.when, '11/22（日）00:30–02:30');
    });
  });
}
