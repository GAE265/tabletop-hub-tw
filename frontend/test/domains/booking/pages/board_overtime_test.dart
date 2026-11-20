// 店家看板標示超時的訂位（spec：add-booking-notifications 的 booking-board-overtime）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/pages/widgets/seating_plan.dart';

import '../../../support/fakes.dart';
import 'booking_pages_test.dart' show pumpAt, sampleBooking, staff;

/// sampleBooking 的結束時間：台灣 11/25 16:00（UTC 08:00）。
DateTime utc(int hour, int minute, [int second = 0]) =>
    DateTime.utc(2026, 11, 25, hour, minute, second);

BookingSummary seatedSummary(String status) => BookingSummary(
  id: 7,
  reservationCode: 'BK7',
  userId: 'u-x',
  startAt: '2026-11-25T06:00:00Z',
  endAt: '2026-11-25T08:00:00Z',
  partySize: 4,
  status: status,
);

List<SeatingPlan> plansWith(String status) => [
  SeatingPlan(
    floor: 1,
    tables: [
      TableInfo(
        id: 2,
        tableCode: 'B',
        maxCapacity: 6,
        x: 0,
        y: 0,
        width: 80,
        height: 40,
        shape: 'rectangle',
        status: 'unavailable',
        booking: seatedSummary(status),
      ),
    ],
  ),
];

FakeBookingRepository boardWith(String status) => FakeBookingRepository()
  ..board = [sampleBooking(status: status)]
  ..seatingPlans = plansWith(status);

SeatTone toneOf(WidgetTester tester) =>
    tester.widget<SeatTable>(find.byKey(const Key('seat-table-2'))).tone;

Finder overtimeLabel() => find.byKey(const Key('board-overtime-7'));

void main() {
  testWidgets('已入座、超過結束時間 25 分鐘：訂位卡與座位圖都標示', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: boardWith('seated'),
      user: staff,
      clock: () => utc(8, 25),
    );
    expect(overtimeLabel(), findsOneWidget);
    expect(
      find.descendant(of: overtimeLabel(), matching: find.text('已超時 25 分鐘')),
      findsOneWidget,
    );
    expect(toneOf(tester), SeatTone.overtime);
    expect(
      find.descendant(
        of: find.byKey(const Key('seating-legend')),
        matching: find.text('已超時'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('已入座、還沒到結束時間：沒有超時標示', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: boardWith('seated'),
      user: staff,
      clock: () => utc(7, 50),
    );
    expect(overtimeLabel(), findsNothing);
    expect(toneOf(tester), SeatTone.occupied);
  });

  for (final status in ['confirmed', 'completed']) {
    testWidgets('$status 的訂位過了結束時間：沒有超時標示', (tester) async {
      await pumpAt(
        tester,
        '/booking/board',
        repo: boardWith(status),
        user: staff,
        clock: () => utc(9, 0),
      );
      expect(overtimeLabel(), findsNothing);
      expect(toneOf(tester), SeatTone.occupied);
    });
  }

  testWidgets('看板開著，時間走過結束時間：一分鐘內出現標示', (tester) async {
    var now = utc(7, 59, 30);
    await pumpAt(
      tester,
      '/booking/board',
      repo: boardWith('seated'),
      user: staff,
      clock: () => now,
    );
    expect(overtimeLabel(), findsNothing);

    now = utc(8, 1);
    await tester.pump(const Duration(minutes: 1));
    expect(
      find.descendant(of: overtimeLabel(), matching: find.text('已超時 1 分鐘')),
      findsOneWidget,
    );
    expect(toneOf(tester), SeatTone.overtime);
  });

  testWidgets('玩家的座位圖：沒有「已超時」', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(const FakeAppFonts()),
        home: Scaffold(
          body: SeatingPlanView(
            plans: plansWith('seated'),
            staffView: false,
            now: utc(9, 0),
          ),
        ),
      ),
    );
    expect(find.text('已超時'), findsNothing);
    expect(toneOf(tester), SeatTone.mine);
  });

  test('seatTone：只有店員看板、已入座且超時才是 overtime', () {
    final seat = groupSeats(plansWith('seated').single.tables).single;
    expect(seatTone(seat, staffView: true, now: utc(8, 25)), SeatTone.overtime);
    expect(seatTone(seat, staffView: true, now: utc(7, 0)), SeatTone.occupied);
    expect(seatTone(seat, staffView: true), SeatTone.occupied);
    expect(seatTone(seat, staffView: false, now: utc(8, 25)), SeatTone.mine);
  });
}
