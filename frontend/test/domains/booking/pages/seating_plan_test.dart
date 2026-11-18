// 座位圖正式頁面：店家看板的座位圖、我的訂位的「看座位」。
// 查詢與狀態已由 booking_state_test 涵蓋，這裡確認畫面、顏色分類、權限與 RWD。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/pages/widgets/seating_plan.dart';

import '../../../support/fakes.dart';
import 'booking_pages_test.dart'
    show admin, player, pumpAt, sampleBooking, staff, tapKey;

TableInfo seat(
  int id,
  String code, {
  int x = 0,
  int y = 0,
  String status = 'available',
  BookingSummary? booking,
}) => TableInfo(
  id: id,
  tableCode: code,
  maxCapacity: 6,
  x: x,
  y: y,
  width: 80,
  height: 40,
  shape: 'rectangle',
  status: status,
  booking: booking,
);

/// 台灣時間 11/25 14:00–16:00（或 18:00–20:00）的訂位摘要。
BookingSummary summary(int id, {bool evening = false, String user = 'u-x'}) =>
    BookingSummary(
      id: id,
      reservationCode: 'BK$id',
      userId: user,
      startAt: evening ? '2026-11-25T10:00:00Z' : '2026-11-25T06:00:00Z',
      endAt: evening ? '2026-11-25T12:00:00Z' : '2026-11-25T08:00:00Z',
      partySize: 4,
      status: 'confirmed',
    );

/// 店員看到的：A 空桌；B 這天有兩筆訂位（後端每筆一列）；B1 的 H 空桌。
final staffPlans = [
  SeatingPlan(
    floor: 1,
    tables: [
      seat(1, 'A'),
      seat(2, 'B', x: 120, status: 'unavailable', booking: summary(7)),
      seat(
        2,
        'B',
        x: 120,
        status: 'unavailable',
        booking: summary(8, evening: true),
      ),
    ],
  ),
  SeatingPlan(floor: -1, tables: [seat(8, 'H')]),
];

/// 玩家看到的：A 空桌；B 別人訂的（沒有訂位資料）；C 自己訂的。
final playerPlans = [
  SeatingPlan(
    floor: 1,
    tables: [
      seat(1, 'A'),
      seat(2, 'B', x: 120, status: 'unavailable'),
      seat(
        3,
        'C',
        y: 80,
        status: 'unavailable',
        booking: summary(7, user: 'u-player'),
      ),
    ],
  ),
];

SeatTone toneOf(WidgetTester tester, int id) =>
    tester.widget<SeatTable>(find.byKey(Key('seat-table-$id'))).tone;

void main() {
  group('桌子分組與顏色', () {
    test('同一張桌有多筆訂位：合併成一張桌，訂位依序列出', () {
      final groups = groupSeats(staffPlans.first.tables);
      expect([for (final g in groups) g.table.tableCode], ['A', 'B']);
      expect(
        [for (final b in groups[1].bookings) b.reservationCode],
        ['BK7', 'BK8'],
      );
      expect(groups[0].bookings, isEmpty);
    });

    test('店員：有訂位一律是「已訂」，不會是「你的訂位」', () {
      final groups = groupSeats(staffPlans.first.tables);
      expect(seatTone(groups[0], staffView: true), SeatTone.available);
      expect(seatTone(groups[1], staffView: true), SeatTone.occupied);
    });

    test('玩家：自己的訂位是「你的訂位」，別人的是「已訂」', () {
      final groups = groupSeats(playerPlans.first.tables);
      expect(seatTone(groups[0], staffView: false), SeatTone.available);
      expect(seatTone(groups[1], staffView: false), SeatTone.occupied);
      expect(seatTone(groups[2], staffView: false), SeatTone.mine);
    });

    test('樓層名稱：1→1F、-1→B1', () {
      expect(floorLabel(1), '1F');
      expect(floorLabel(2), '2F');
      expect(floorLabel(-1), 'B1');
    });
  });

  group('店家看板的座位圖', () {
    testWidgets('依座標畫出桌子，顯示桌號，空桌與已訂分色，有圖例', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);

      final call = repo.seatingCalls.single;
      expect(call.shopId, 's-b');
      expect(call.from, endsWith('T00:00:00+08:00'));
      expect(call.to, endsWith('T23:59:59+08:00'));

      expect(find.byKey(const Key('board-seating')), findsOneWidget);
      expect(find.byKey(const Key('seat-table-1')), findsOneWidget);
      // B 有兩筆訂位，只畫一次
      expect(find.byKey(const Key('seat-table-2')), findsOneWidget);
      expect(toneOf(tester, 1), SeatTone.available);
      expect(toneOf(tester, 2), SeatTone.occupied);
      final a = tester.getTopLeft(find.byKey(const Key('seat-table-1')));
      final b = tester.getTopLeft(find.byKey(const Key('seat-table-2')));
      expect(b.dx - a.dx, 120);

      final legend = find.byKey(const Key('seating-legend'));
      expect(find.descendant(of: legend, matching: find.text('空桌')), findsOne);
      expect(find.descendant(of: legend, matching: find.text('已訂')), findsOne);
      expect(
        find.descendant(of: legend, matching: find.text('你的訂位')),
        findsNothing,
      );
    });

    testWidgets('切換樓層：只顯示該樓層的桌子', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(find.byKey(const Key('seat-table-8')), findsNothing);

      await tapKey(tester, 'seating-floor-B1');
      expect(find.byKey(const Key('seat-table-8')), findsOneWidget);
      expect(find.byKey(const Key('seat-table-1')), findsNothing);
    });

    testWidgets('後端先回 B1：仍預設顯示 1F，樓層依 1F、B1 排列', (tester) async {
      final repo = FakeBookingRepository()
        ..seatingPlans = staffPlans.reversed.toList();
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(find.byKey(const Key('seat-table-1')), findsOneWidget);
      expect(find.byKey(const Key('seat-table-8')), findsNothing);
      final first = tester.getTopLeft(
        find.byKey(const Key('seating-floor-1F')),
      );
      final second = tester.getTopLeft(
        find.byKey(const Key('seating-floor-B1')),
      );
      expect(first.dx, lessThan(second.dx));
    });

    testWidgets('只有一個樓層：不顯示樓層切換', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = [staffPlans.first];
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(find.byKey(const Key('seating-floor-1F')), findsNothing);
      expect(find.byKey(const Key('seat-table-1')), findsOneWidget);
    });

    testWidgets('換日期：座位圖用新日期重新查詢', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      final first = repo.seatingCalls.single.from!;

      await tapKey(tester, 'board-date');
      // 選同一個月的另一天（今天是 1 號就選 2 號）
      final day = int.parse(first.substring(8, 10));
      final other = day == 1 ? 2 : 1;
      await tester.tap(find.text('$other').last);
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      expect(repo.seatingCalls, hasLength(2));
      expect(repo.seatingCalls.last.from, isNot(first));
      expect(repo.seatingCalls.last.from, endsWith('T00:00:00+08:00'));
    });

    testWidgets('點已訂的桌：列出這段時間的所有訂位', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);

      await tapKey(tester, 'seat-table-2');
      final sheet = find.byKey(const Key('seat-detail'));
      expect(sheet, findsOneWidget);
      Finder inSheet(String text) =>
          find.descendant(of: sheet, matching: find.textContaining(text));
      expect(inSheet('B 桌'), findsOneWidget);
      expect(inSheet('最多 6 人'), findsOneWidget);
      expect(inSheet('BK7'), findsOneWidget);
      expect(inSheet('BK8'), findsOneWidget);
      expect(inSheet('11/25（三）14:00–16:00'), findsOneWidget);
      expect(inSheet('11/25（三）18:00–20:00'), findsOneWidget);
      expect(inSheet('4 人'), findsNWidgets(2));
      expect(inSheet('已確認'), findsNWidgets(2));
    });

    testWidgets('點空桌：顯示桌號、人數上限與「這段時間沒有訂位」', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);

      await tapKey(tester, 'seat-table-1');
      final sheet = find.byKey(const Key('seat-detail'));
      Finder inSheet(String text) =>
          find.descendant(of: sheet, matching: find.textContaining(text));
      expect(inSheet('A 桌'), findsOneWidget);
      expect(inSheet('最多 6 人'), findsOneWidget);
      expect(inSheet('這段時間沒有訂位'), findsOneWidget);
    });

    testWidgets('載入失敗：顯示中文錯誤，按「重試」後顯示座位圖', (tester) async {
      final repo = FakeBookingRepository()
        ..seatingPlans = staffPlans
        ..seatingError = const ApiException(
          code: 'BOOKING_SHOP_NOT_FOUND',
          message: '店家不存在',
        );
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(find.text('店家不存在'), findsOneWidget);
      expect(find.textContaining('BOOKING_SHOP_NOT_FOUND'), findsNothing);

      repo.seatingError = null;
      await tapKey(tester, 'board-retry');
      expect(find.text('店家不存在'), findsNothing);
      expect(find.byKey(const Key('seat-table-1')), findsOneWidget);
    });

    testWidgets('店家沒有桌子：顯示「這間店還沒有座位圖」', (tester) async {
      await pumpAt(tester, '/booking/board', user: staff);
      expect(find.text('這間店還沒有座位圖'), findsOneWidget);
    });

    testWidgets('玩家：維持沒有權限，不查詢座位圖', (tester) async {
      final repo = await pumpAt(tester, '/booking/board');
      expect(find.byKey(const Key('board-no-permission')), findsOneWidget);
      expect(repo.seatingCalls, isEmpty);
    });

    testWidgets('管理員：選店家後才查詢座位圖', (tester) async {
      final repo = FakeBookingRepository()..seatingPlans = staffPlans;
      await pumpAt(tester, '/booking/board', repo: repo, user: admin);
      expect(repo.seatingCalls, isEmpty);
      await tester.tap(find.byKey(const Key('booking-shop')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('甲店').last);
      await tester.pumpAndSettle();
      expect(repo.seatingCalls.single.shopId, 's-a');
    });

    testWidgets('手機：座位圖在訂位列表上方；桌機：左右並排', (tester) async {
      final repo = FakeBookingRepository()
        ..seatingPlans = staffPlans
        ..board = [sampleBooking()];
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      var seating = tester.getRect(find.byKey(const Key('board-seating')));
      var card = tester.getRect(find.byKey(const Key('board-card-7')));
      expect(card.top, greaterThanOrEqualTo(seating.bottom));

      await pumpAt(
        tester,
        '/booking/board',
        repo: repo,
        user: staff,
        size: const Size(1280, 900),
      );
      seating = tester.getRect(find.byKey(const Key('board-seating')));
      card = tester.getRect(find.byKey(const Key('board-card-7')));
      expect(card.left, greaterThanOrEqualTo(seating.right));
    });
  });

  group('我的訂位：看座位', () {
    testWidgets('已確認、已入座才有「看座位」', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [
          sampleBooking(id: 1),
          sampleBooking(id: 2, status: 'seated'),
          sampleBooking(id: 3, status: 'cancelled'),
          sampleBooking(id: 4, status: 'completed'),
        ];
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);
      expect(find.byKey(const Key('booking-seats-1')), findsOneWidget);
      expect(find.byKey(const Key('booking-seats-2')), findsOneWidget);
      expect(find.byKey(const Key('booking-seats-3')), findsNothing);
      expect(find.byKey(const Key('booking-seats-4')), findsNothing);
    });

    testWidgets('按「看座位」：用那筆訂位的店家與時段查詢，自己的桌標成「你的訂位」', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking()]
        ..seatingPlans = playerPlans;
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);

      await tapKey(tester, 'booking-seats-7');
      final call = repo.seatingCalls.single;
      expect(call.shopId, 's-a');
      expect(call.from, '2026-11-25T06:00:00Z');
      expect(call.to, '2026-11-25T08:00:00Z');

      final sheet = find.byKey(const Key('booking-seats-sheet'));
      expect(
        find.descendant(of: sheet, matching: find.textContaining('甲店')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: sheet,
          matching: find.textContaining('11/25（三）14:00–16:00'),
        ),
        findsOneWidget,
      );
      expect(toneOf(tester, 1), SeatTone.available);
      expect(toneOf(tester, 2), SeatTone.occupied);
      expect(toneOf(tester, 3), SeatTone.mine);
      final legend = find.byKey(const Key('seating-legend'));
      expect(
        find.descendant(of: legend, matching: find.text('你的訂位')),
        findsOne,
      );
    });

    testWidgets('點自己的桌：顯示自己的訂位', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking()]
        ..seatingPlans = playerPlans;
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);
      await tapKey(tester, 'booking-seats-7');

      await tapKey(tester, 'seat-table-3');
      final sheet = find.byKey(const Key('seat-detail'));
      Finder inSheet(String text) =>
          find.descendant(of: sheet, matching: find.textContaining(text));
      expect(inSheet('你的訂位'), findsOneWidget);
      expect(inSheet('BK7'), findsOneWidget);
      expect(inSheet('4 人'), findsOneWidget);
    });

    testWidgets('點別人訂的桌：只顯示「此時段已被預訂」', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking()]
        ..seatingPlans = playerPlans;
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);
      await tapKey(tester, 'booking-seats-7');

      await tapKey(tester, 'seat-table-2');
      final sheet = find.byKey(const Key('seat-detail'));
      Finder inSheet(String text) =>
          find.descendant(of: sheet, matching: find.textContaining(text));
      expect(inSheet('B 桌'), findsOneWidget);
      expect(inSheet('此時段已被預訂'), findsOneWidget);
      expect(inSheet('BK'), findsNothing);
    });

    testWidgets('載入失敗：顯示中文錯誤，按「重試」後顯示座位圖', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking()]
        ..seatingPlans = playerPlans
        ..seatingError = const ApiException(
          code: 'BOOKING_SHOP_NOT_FOUND',
          message: '店家不存在',
        );
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);
      await tapKey(tester, 'booking-seats-7');
      final sheet = find.byKey(const Key('booking-seats-sheet'));
      expect(
        find.descendant(of: sheet, matching: find.text('店家不存在')),
        findsOneWidget,
      );

      repo.seatingError = null;
      await tapKey(tester, 'seating-retry');
      expect(find.byKey(const Key('seat-table-3')), findsOneWidget);
      expect(repo.seatingCalls, hasLength(2));
    });

    testWidgets('店家沒有桌子：顯示「這間店還沒有座位圖」', (tester) async {
      final repo = FakeBookingRepository()..mine = [sampleBooking()];
      await pumpAt(tester, '/booking/mine', repo: repo, user: player);
      await tapKey(tester, 'booking-seats-7');
      expect(find.text('這間店還沒有座位圖'), findsOneWidget);
    });
  });
}
