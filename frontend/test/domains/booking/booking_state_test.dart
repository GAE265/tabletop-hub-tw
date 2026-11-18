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
}
