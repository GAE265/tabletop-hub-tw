import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/dev/state/dev_user_state.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../data/video_studio_models.dart';
import '../../state/video_job_state.dart';
import 'notice_banner.dart';

/// 專案步驟（`step`）給店員看的名稱。
String videoStepLabel(String step) => switch (step) {
  'rulebook' => '拍規則書',
  'pages' => '選頁（舊）',
  'draft' => '草稿',
  'assets' => '拍素材',
  'render' => '產生影片',
  'done' => '完成',
  _ => step,
};

/// 只有店家人員與管理員能用影片功能；其他身分不建立 [child]（也就不會呼叫 API）。
class VideoAccessGuard extends ConsumerWidget {
  const VideoAccessGuard({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final role = ref.watch(currentDevUserProvider)?.role;
    if (role == 'shop_staff' || role == 'admin') return child;
    return Scaffold(
      key: const Key('video-no-permission'),
      appBar: AppBar(title: const Text('規則影片')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.large),
          child: Text(
            '只有店家人員可以使用影片功能',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
      ),
    );
  }
}

/// 影片頁的內容寬度：手機佔滿，平板與桌機置中限寬。
class VideoPageBody extends StatelessWidget {
  const VideoPageBody({
    required this.child,
    this.shrinkHeight = false,
    super.key,
  });

  final Widget child;

  /// 高度只包住內容（放在底部按鈕列時用，否則會撐滿整個畫面）。
  final bool shrinkHeight;

  @override
  Widget build(BuildContext context) {
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    return Align(
      alignment: Alignment.topCenter,
      heightFactor: shrinkHeight ? 1 : null,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}

/// 頁面底部的按鈕列。
class VideoBottomActions extends StatelessWidget {
  const VideoBottomActions({required this.children, super.key});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      elevation: 2,
      child: SafeArea(
        top: false,
        child: VideoPageBody(
          shrinkHeight: true,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.medium),
            child: Row(
              children: [
                for (final (i, child) in children.indexed) ...[
                  if (i > 0) const SizedBox(width: AppSpacing.small),
                  Expanded(child: child),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 工作進度卡片（外觀決定：草稿用階段文字加不確定進度的橫條，只有產生影片才顯示百分比；
/// 失敗只寫店員看得懂的原因與「重試」）。沒有工作時不佔空間。
class VideoJobCard extends ConsumerWidget {
  const VideoJobCard({
    required this.projectId,
    this.showDone = true,
    super.key,
  });

  final String projectId;

  /// 完成的工作要不要顯示（草稿頁本身就是結果，不必再顯示）。
  final bool showDone;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(videoJobProvider(projectId));
    final job = state.job;
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final children = <Widget>[
      if (state.error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.medium),
          child: NoticeBanner(text: state.error!, isError: true),
        ),
    ];
    if (job != null) {
      // 依工作種類決定「重試」做什麼、完成後去哪裡
      final notifier = ref.read(videoJobProvider(projectId).notifier);
      final render = job.kind == 'render';
      final VoidCallback retry = render
          ? notifier.startRender
          : notifier.startDraft;
      final (doneLabel, donePath) = render
          ? ('看影片', '/videos/$projectId/watch')
          : ('查看草稿', '/videos/$projectId/draft');
      final card = switch (job.status) {
        VideoJobStatus.queued || VideoJobStatus.running => _card(
          context,
          key: const Key('video-job-running'),
          children: [
            Text(job.message ?? '準備中', style: text.titleMedium),
            const SizedBox(height: AppSpacing.small),
            if (job.kind == 'render') ...[
              LinearProgressIndicator(value: job.progress),
              const SizedBox(height: AppSpacing.xSmall),
              Text('${(job.progress * 100).round()}%', style: text.bodySmall),
            ] else
              const LinearProgressIndicator(),
            const SizedBox(height: AppSpacing.small),
            Text(
              '可以離開這頁，完成後回來看',
              style: text.bodySmall!.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ),
        VideoJobStatus.succeeded when showDone => _card(
          context,
          key: const Key('video-job-done'),
          children: [
            Row(
              children: [
                Icon(Icons.check_circle, color: scheme.primary),
                const SizedBox(width: AppSpacing.small),
                Expanded(
                  child: Text(
                    job.kind == 'render' ? '影片已產生' : '草稿已產生',
                    style: text.titleMedium,
                  ),
                ),
                TextButton(
                  onPressed: () => context.go(donePath),
                  child: Text(doneLabel),
                ),
              ],
            ),
          ],
        ),
        VideoJobStatus.failed => _card(
          context,
          key: const Key('video-job-failed'),
          color: scheme.errorContainer,
          children: [
            Text(
              job.error ?? '沒有完成，請再試一次',
              style: text.bodyLarge!.copyWith(color: scheme.onErrorContainer),
            ),
            const SizedBox(height: AppSpacing.small),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(onPressed: retry, child: const Text('重試')),
            ),
          ],
        ),
        _ => null,
      };
      if (card != null) {
        children.add(
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: card,
          ),
        );
      }
    }
    if (children.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    );
  }

  Widget _card(
    BuildContext context, {
    required Key key,
    required List<Widget> children,
    Color? color,
  }) => Card(
    key: key,
    color: color,
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.medium),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    ),
  );
}

/// 產生影片前還缺什麼（素材清單與產生影片頁共用）。素材用給店員看的名稱，不顯示 asset_key。
class VideoReadinessCard extends StatelessWidget {
  const VideoReadinessCard({
    required this.readiness,
    this.names = const {},
    super.key,
  });

  final VideoReadiness readiness;

  /// asset_key → 給店員看的名稱（從草稿的素材清單來）。
  final Map<String, String> names;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    if (readiness.ready) {
      return Card(
        key: const Key('video-readiness'),
        child: ListTile(
          leading: Icon(Icons.check_circle, color: scheme.primary),
          title: const Text('可以產生影片'),
        ),
      );
    }
    return Card(
      key: const Key('video-readiness'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('還缺這些才能產生影片', style: text.titleSmall),
            const SizedBox(height: AppSpacing.small),
            for (final photo in readiness.missingPhotos)
              Text(
                '拍照：${photo.label.isNotEmpty ? photo.label : photo.reason}'
                '${photo.skippable ? '（可略過）' : ''}',
                style: text.bodyMedium,
              ),
            for (final region in readiness.missingRegions)
              Text(
                '標區域：${names[region.assetKey] ?? '素材'}的「${region.region}」',
                style: text.bodyMedium,
              ),
            for (final asset in readiness.unsupported)
              Text(
                asset.message,
                style: text.bodyMedium!.copyWith(color: scheme.error),
              ),
          ],
        ),
      ),
    );
  }
}
