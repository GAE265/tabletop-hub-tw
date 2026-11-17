import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/state/booking_state.dart';

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
}
