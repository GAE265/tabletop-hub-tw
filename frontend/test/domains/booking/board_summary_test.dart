// 店家看板的統計、篩選與剩餘時間（Stitch 版面）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/state/board_summary.dart';

/// 台灣 11/25 14:00–16:00（UTC 06:00–08:00）。
Booking booking(int id, String status, {List<String> tables = const ['T1']}) =>
    Booking(
      id: id,
      reservationCode: 'BK$id',
      shopId: 's-a',
      shopName: '',
      startAt: '2026-11-25T06:00:00Z',
      endAt: '2026-11-25T08:00:00Z',
      partySize: 4,
      status: status,
      tableCodes: tables,
      estimatedFee: const Fee(billableHours: '2.00', venueFee: '480.00'),
    );

TableInfo table(int id, String code) => TableInfo(
  id: id,
  tableCode: code,
  maxCapacity: 4,
  x: 0,
  y: 0,
  width: 40,
  height: 40,
  shape: 'rectangle',
  status: 'available',
);

DateTime utc(int hour, int minute) => DateTime.utc(2026, 11, 25, hour, minute);

void main() {
  final bookings = [
    booking(1, 'seated', tables: ['T1']),
    booking(2, 'confirmed', tables: ['T2']),
    booking(3, 'cancelled', tables: ['T3']),
  ];

  group('篩選', () {
    test('還沒到結束時間：已入座算進行中，已確認算待到店', () {
      final now = utc(7, 0);
      List<int> ids(BoardFilter f) =>
          filterBoard(bookings, f, now).map((b) => b.id).toList();
      expect(ids(BoardFilter.all), [1, 2, 3]);
      expect(ids(BoardFilter.seated), [1]);
      expect(ids(BoardFilter.waiting), [2]);
      expect(ids(BoardFilter.overtime), isEmpty);
    });

    test('已入座超過結束時間：算已超時，不算進行中', () {
      final now = utc(8, 10);
      expect(
        filterBoard(bookings, BoardFilter.overtime, now).map((b) => b.id),
        [1],
      );
      expect(filterBoard(bookings, BoardFilter.seated, now), isEmpty);
    });

    test('各篩選的筆數', () {
      final now = utc(7, 0);
      expect(boardCount(bookings, BoardFilter.all, now), 3);
      expect(boardCount(bookings, BoardFilter.seated, now), 1);
      expect(boardCount(bookings, BoardFilter.waiting, now), 1);
    });
  });

  group('剩餘時間', () {
    test('已入座、還沒到結束時間：剩幾分鐘（不足一分鐘也算一分鐘）', () {
      expect(
        remainingMinutes('seated', '2026-11-25T08:00:00Z', utc(7, 15)),
        45,
      );
      expect(
        remainingMinutes(
          'seated',
          '2026-11-25T08:00:00Z',
          DateTime.utc(2026, 11, 25, 7, 59, 30),
        ),
        1,
      );
    });

    test('已經到結束時間，或不是已入座：沒有剩餘時間', () {
      expect(
        remainingMinutes('seated', '2026-11-25T08:00:00Z', utc(8, 0)),
        isNull,
      );
      expect(
        remainingMinutes('confirmed', '2026-11-25T08:00:00Z', utc(7, 0)),
        isNull,
      );
    });
  });

  group('統計', () {
    final plans = [
      SeatingPlan(
        floor: 1,
        // 同一張桌在查詢時段有多筆訂位時會出現多次，只算一次
        tables: [
          table(1, 'T1'),
          table(1, 'T1'),
          table(2, 'T2'),
          table(3, 'T3'),
        ],
      ),
      SeatingPlan(floor: 2, tables: [table(4, 'B1')]),
    ];

    test('全店桌數、使用中、已超時、空桌', () {
      final stats = boardStats(plans, bookings, utc(8, 10));
      expect(stats.total, 4);
      expect(stats.inUse, 1);
      expect(stats.overtime, 1);
      expect(stats.free, 3);
    });

    test('沒有座位圖：桌數與空桌都是 0', () {
      final stats = boardStats(const [], bookings, utc(7, 0));
      expect(stats.total, 0);
      expect(stats.free, 0);
    });
  });
}
