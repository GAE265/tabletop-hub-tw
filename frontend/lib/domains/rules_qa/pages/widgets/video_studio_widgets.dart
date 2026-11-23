import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
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

/// 步驟條的一步：名稱與圖示。
typedef VideoStep = ({String label, IconData icon});

/// 規則影片的步驟（Stitch 版面的步驟條）：拍規則書的專案多一步「拍規則書」。
List<VideoStep> videoSteps({required bool rulebookPhotos}) => [
  if (rulebookPhotos) (label: '拍規則書', icon: Icons.menu_book_outlined),
  (label: '生成草稿', icon: Icons.edit_note),
  (label: '拍攝素材', icon: Icons.photo_camera_outlined),
  (label: '產生影片', icon: Icons.movie_outlined),
];

/// 橫向步驟條：做過的步驟是綠色打勾，目前這一步是橘色，之後的是灰色；中間用線連起來。
class VideoStepper extends StatelessWidget {
  const VideoStepper({required this.steps, required this.current, super.key});

  final List<VideoStep> steps;

  /// 目前在第幾步（從 0 開始）。
  final int current;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    Widget line(bool done) => Expanded(
      child: Container(
        height: AppSizes.stepLine,
        // 對齊圓點的中間
        margin: const EdgeInsets.only(
          top: (AppSizes.stepDot - AppSizes.stepLine) / 2,
        ),
        color: done ? AppColors.sage : AppColors.cardEdge,
      ),
    );
    Widget step(int i, VideoStep s) {
      final done = i < current;
      final now = i == current;
      final color = done
          ? AppColors.sage
          : now
          ? AppColors.primary
          : AppColors.neutralTint;
      final column = Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: AppSizes.stepDot,
            height: AppSizes.stepDot,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: now ? AppShadows.soft : null,
            ),
            child: Icon(
              done ? Icons.check : s.icon,
              size: AppSizes.inlineIcon,
              color: done || now ? AppColors.surface : AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: AppSpacing.xSmall),
          Text(
            s.label,
            style: text.labelMedium!.copyWith(
              color: now ? AppColors.primaryText : AppColors.inkMuted,
              fontWeight: now ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ],
      );
      return now
          ? KeyedSubtree(key: const Key('video-stepper-current'), child: column)
          : column;
    }

    return Row(
      key: const Key('video-stepper'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final (i, s) in steps.indexed) ...[
          if (i > 0) line(i <= current),
          step(i, s),
        ],
      ],
    );
  }
}
