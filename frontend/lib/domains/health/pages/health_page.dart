import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../state/health_state.dart';

/// health 正式頁面（示範用，之後由永傑接手）：只呼叫 `state/`，樣式全來自主題。
class HealthPage extends ConsumerWidget {
  const HealthPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthProvider);
    final theme = Theme.of(context);

    final Widget content = health.when(
      loading: () => const CircularProgressIndicator(),
      error: (error, _) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.error_outline, color: theme.colorScheme.error),
          const SizedBox(height: AppSpacing.small),
          Text(error is ApiException ? error.message : '發生未知錯誤'),
          const SizedBox(height: AppSpacing.medium),
          FilledButton(
            onPressed: () => ref.read(healthProvider.notifier).reload(),
            child: const Text('重試'),
          ),
        ],
      ),
      data: (status) {
        final healthy = status.status == 'ok';
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              healthy ? Icons.check_circle : Icons.warning_amber,
              color: healthy ? AppColors.success : AppColors.warning,
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              healthy ? '服務正常' : '服務異常',
              style: theme.textTheme.headlineSmall,
            ),
            Text('狀態：${status.status}　資料庫：${status.database}'),
            const SizedBox(height: AppSpacing.medium),
            FilledButton(
              onPressed: () => ref.read(healthProvider.notifier).reload(),
              child: const Text('重新檢查'),
            ),
          ],
        );
      },
    );

    return Scaffold(
      key: const Key('health-page'),
      appBar: AppBar(title: const Text('遊任有娛')),
      body: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth:
                AppSpacing.contentMaxWidth(context.screenSize) ??
                double.infinity,
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: content,
          ),
        ),
      ),
    );
  }
}
