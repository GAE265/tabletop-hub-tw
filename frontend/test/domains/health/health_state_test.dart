import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';
import 'package:tabletop_hub/domains/health/state/health_state.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer(FakeHealthRepository repo) {
  final container = ProviderContainer(
    overrides: [healthRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('載入中 → 成功', () async {
    final container = makeContainer(
      FakeHealthRepository(
        result: const HealthStatus(status: 'ok', database: 'up'),
      ),
    );
    expect(container.read(healthProvider).isLoading, isTrue);
    final status = await container.read(healthProvider.future);
    expect(status.status, 'ok');
    expect(status.database, 'up');
  });

  test('後端回報 degraded 也是成功狀態（資料庫 down）', () async {
    final container = makeContainer(
      FakeHealthRepository(
        result: const HealthStatus(status: 'degraded', database: 'down'),
      ),
    );
    final status = await container.read(healthProvider.future);
    expect(status.database, 'down');
  });

  test('錯誤：保留 ApiException，reload 後可恢復', () async {
    final repo = FakeHealthRepository(
      error: const ApiException(code: 'NETWORK_ERROR', message: '無法連線'),
    );
    final container = makeContainer(repo);
    await expectLater(
      container.read(healthProvider.future),
      throwsA(isA<ApiException>()),
    );
    expect(container.read(healthProvider).hasError, isTrue);

    repo
      ..error = null
      ..result = const HealthStatus(status: 'ok', database: 'up');
    await container.read(healthProvider.notifier).reload();
    expect(container.read(healthProvider).value?.status, 'ok');
  });
}
