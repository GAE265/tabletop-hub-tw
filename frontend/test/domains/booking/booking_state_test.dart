import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/state/booking_state.dart';

import 'package:tabletop_hub/domains/booking/data/booking.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer(FakeBookingRepository repo) {
  final container = ProviderContainer(
    overrides: [bookingRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}

/// 店家看板上一筆已確認的訂位。
Booking boardBooking({int id = 7, String status = 'confirmed'}) => Booking(
  id: id,
  reservationCode: 'BK$id',
  shopId: 's-a',
  shopName: '甲店',
  startAt: '2026-11-25T06:00:00Z',
  endAt: '2026-11-25T08:00:00Z',
  partySize: 4,
  status: status,
  tableCodes: const ['T1', 'T2'],
  estimatedFee: const Fee(billableHours: '2.00', venueFee: '480.00'),
);

void main() {
  test('載入店家成功：填入店家清單', () async {
    final container = makeContainer(FakeBookingRepository());
    await container.read(bookingProvider.notifier).loadShops();
    final state = container.read(bookingProvider);
    expect(state.shops.map((s) => s.name), ['甲店', '乙店']);
    expect(state.isError, isFalse);
  });

  test('載入店家失敗：顯示錯誤訊息，重新載入後可恢復', () async {
    final repo = FakeBookingRepository(
      shopError: const ApiException(code: 'NETWORK_ERROR', message: '無法連線'),
    );
    final container = makeContainer(repo);
    await container.read(bookingProvider.notifier).loadShops();
    expect(container.read(bookingProvider).isError, isTrue);

    repo.shopError = null;
    await container.read(bookingProvider.notifier).loadShops();
    final state = container.read(bookingProvider);
    expect(state.isError, isFalse);
    expect(state.shops.length, 2);
  });

  test('沒有店家：清單為空', () async {
    final container = makeContainer(FakeBookingRepository(shops: const []));
    await container.read(bookingProvider.notifier).loadShops();
    expect(container.read(bookingProvider).shops, isEmpty);
  });

  group('座位圖', () {
    test('載入座位圖成功', () async {
      final plans = [
        SeatingPlan(floor: 1, tables: [
          TableInfo(
            id: 1, tableCode: 'A', maxCapacity: 6,
            x: 50, y: 50, width: 160, height: 100,
            shape: 'rectangle', status: 'available',
          ),
          TableInfo(
            id: 2, tableCode: 'B', maxCapacity: 6,
            x: 250, y: 50, width: 160, height: 100,
            shape: 'rectangle', status: 'unavailable',
            booking: BookingSummary(
              id: 100, reservationCode: 'BK001', userId: 'u-player',
              startAt: '2026-11-26T06:00:00Z', endAt: '2026-11-26T08:00:00Z',
              partySize: 4, status: 'confirmed',
            ),
          ),
        ]),
      ];
      final repo = FakeBookingRepository(seatingPlans: plans);
      final container = makeContainer(repo);

      await container.read(bookingProvider.notifier).loadSeatingPlan('s-a');
      final state = container.read(bookingProvider);

      expect(state.seatingPlan.length, 1);
      expect(state.seatingPlan[0].floor, 1);
      expect(state.seatingPlan[0].tables.length, 2);
      expect(state.seatingPlan[0].tables[0].tableCode, 'A');
      expect(state.seatingPlan[0].tables[0].status, 'available');
      expect(state.seatingPlan[0].tables[1].status, 'unavailable');
      expect(state.seatingPlan[0].tables[1].booking, isNotNull);
      expect(repo.seatingCallCount, 1);
      expect(state.isError, isFalse);
    });

    test('點擊桌子更新 selectedTable', () {
      final table = TableInfo(
        id: 1, tableCode: 'A', maxCapacity: 6,
        x: 50, y: 50, width: 160, height: 100,
        shape: 'rectangle', status: 'available',
      );
      final repo = FakeBookingRepository();
      final container = makeContainer(repo);

      container.read(bookingProvider.notifier).selectTable(table);
      final state = container.read(bookingProvider);

      expect(state.selectedTable, table);
      expect(state.message, 'A');
    });

    test('座位圖載入失敗顯示錯誤', () async {
      final repo = FakeBookingRepository(
        seatingError: const ApiException(code: 'SHOP_NOT_FOUND', message: '店家不存在'),
      );
      final container = makeContainer(repo);

      await container.read(bookingProvider.notifier).loadSeatingPlan('bad-id');
      final state = container.read(bookingProvider);

      expect(state.isError, isTrue);
      expect(state.message, contains('SHOP_NOT_FOUND'));
    });
  });

  group('換桌', () {
    test('進入與離開選桌模式：只記下訂位 id，不送請求', () async {
      final repo = FakeBookingRepository()..board = [boardBooking()];
      final container = makeContainer(repo);
      final n = container.read(bookingProvider.notifier);

      n.startChangeTable(7);
      expect(container.read(bookingProvider).changeTableFor, 7);

      n.cancelChangeTable();
      final state = container.read(bookingProvider);
      expect(state.changeTableFor, isNull);
      expect(repo.changeTablesCalls, isEmpty);
    });

    test('換桌成功：更新列表桌位並離開選桌模式', () async {
      final repo = FakeBookingRepository()..board = [boardBooking()];
      final container = makeContainer(repo);
      final n = container.read(bookingProvider.notifier);

      await n.loadBoard('s-a', '2026-11-25', '2026-11-25');
      n.startChangeTable(7);
      await n.changeTable(7, [3]);

      final state = container.read(bookingProvider);
      expect(state.changeTableFor, isNull);
      expect(state.isError, isFalse);
      expect(state.message, contains('已換桌至 T3'));
      expect(state.board.single.tableCodes, ['T3']);
      final call = repo.changeTablesCalls.single;
      expect(call.id, 7);
      expect(call.tableIds, [3]);
    });

    test('目標桌已被訂走：顯示錯誤，留在選桌模式且列表不變', () async {
      final repo = FakeBookingRepository()
        ..board = [boardBooking()]
        ..changeTablesError = const ApiException(
          code: 'BOOKING_TABLE_TAKEN',
          message: '這個時段已經沒有空桌',
          statusCode: 409,
        );
      final container = makeContainer(repo);
      final n = container.read(bookingProvider.notifier);

      await n.loadBoard('s-a', '2026-11-25', '2026-11-25');
      n.startChangeTable(7);
      await n.changeTable(7, [2]);

      final state = container.read(bookingProvider);
      expect(state.isError, isTrue);
      expect(state.message, contains('BOOKING_TABLE_TAKEN'));
      expect(state.changeTableFor, 7);
      expect(state.board.single.tableCodes, ['T1', 'T2']);
    });
  });
}
