import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/health_repository.dart';
import '../data/health_status.dart';

/// health 畫面的狀態與操作。參考畫面（prototypes）與正式頁面（pages）共用這一份。
class HealthNotifier extends AsyncNotifier<HealthStatus> {
  @override
  Future<HealthStatus> build() => ref.watch(healthRepositoryProvider).fetch();

  /// 「重新檢查」按鈕：回到載入中，再重新呼叫 `GET /api/v1/health`。
  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(healthRepositoryProvider).fetch(),
    );
  }
}

final healthProvider = AsyncNotifierProvider<HealthNotifier, HealthStatus>(
  HealthNotifier.new,
  retry: (_, _) => null,
);
