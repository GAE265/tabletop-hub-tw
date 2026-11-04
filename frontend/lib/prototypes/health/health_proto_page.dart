import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../domains/health/state/health_state.dart';

/// health 參考畫面：只用預設元件，不調顏色、字型、間距（AGENTS.md 5.4）。
class HealthProtoPage extends ConsumerWidget {
  const HealthProtoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthProvider);
    return Scaffold(
      key: const Key('health-proto-page'),
      appBar: AppBar(title: const Text('health（參考畫面）')),
      body: Center(
        child: health.when(
          loading: () => const CircularProgressIndicator(),
          error: (error, _) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(error is ApiException ? error.message : '發生未知錯誤'),
              ElevatedButton(
                onPressed: () => ref.read(healthProvider.notifier).reload(),
                child: const Text('重試'),
              ),
            ],
          ),
          data: (status) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('服務：${status.status}'),
              Text('資料庫：${status.database}'),
              ElevatedButton(
                onPressed: () => ref.read(healthProvider.notifier).reload(),
                child: const Text('重新檢查'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
