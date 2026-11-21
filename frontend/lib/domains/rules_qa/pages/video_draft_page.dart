import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_draft_state.dart';
import '../state/video_job_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 草稿確認（`/videos/:id/draft`，外觀決定見 design.md）：每段一張卡片，逐句勾選「已檢查」；
/// 頁首直接顯示涵蓋檢查摘要與提示橫幅；出處頁可以點回去改文字。
class VideoDraftPage extends ConsumerStatefulWidget {
  const VideoDraftPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoDraftPage> createState() => _VideoDraftPageState();
}

class _VideoDraftPageState extends ConsumerState<VideoDraftPage> {
  String get _id => widget.projectId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) ref.read(videoJobProvider(_id).notifier).resume();
    });
  }

  void _regenerate() => ref.read(videoJobProvider(_id).notifier).startDraft();

  @override
  Widget build(BuildContext context) {
    final draft = ref.watch(videoDraftProvider(_id));
    final running = ref.watch(videoJobProvider(_id)).running;
    final jobCard = VideoJobCard(
      projectId: _id,
      onRetry: _regenerate,
      showDone: false,
    );
    return Scaffold(
      key: const Key('video-draft-page'),
      appBar: AppBar(title: const Text('確認草稿')),
      bottomNavigationBar: draft.value == null
          ? null
          : VideoBottomActions(
              children: [
                OutlinedButton(
                  key: const Key('video-draft-regenerate'),
                  onPressed: running ? null : _regenerate,
                  child: const Text('重新產生'),
                ),
                // 沒勾完也能確認（外觀決定）；勾選數只是提醒
                FilledButton(
                  key: const Key('video-draft-confirm'),
                  onPressed: () => context.go('/videos/$_id/assets'),
                  child: const Text('確認草稿'),
                ),
              ],
            ),
      body: VideoPageBody(
        child: draft.when(
          skipLoadingOnRefresh: false,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    error is ApiException ? error.message : '發生未知錯誤',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.medium),
                  FilledButton(
                    onPressed: () => ref.invalidate(videoDraftProvider(_id)),
                    child: const Text('重試'),
                  ),
                ],
              ),
            ),
          ),
          data: (value) => value == null
              ? ListView(
                  padding: const EdgeInsets.all(AppSpacing.medium),
                  children: [
                    jobCard,
                    Text(
                      '還沒有草稿',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppSpacing.medium),
                    FilledButton(
                      onPressed: () => context.go('/videos/$_id/pages'),
                      child: const Text('選頁與編輯文字'),
                    ),
                  ],
                )
              : _DraftView(projectId: _id, draft: value, jobCard: jobCard),
        ),
      ),
    );
  }
}

class _DraftView extends ConsumerWidget {
  const _DraftView({
    required this.projectId,
    required this.draft,
    required this.jobCard,
  });

  final String projectId;
  final VideoDraft draft;
  final Widget jobCard;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final checks = ref.watch(subtitleChecksProvider(projectId));
    final (checked, total) = checkedCount(checks, draft);
    final coverage = draft.coverage;
    final text = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        jobCard,
        if (draft.terms.status == 'missing' && draft.terms.message != null)
          _Banner(draft.terms.message!),
        if (draft.pagesStale && draft.pagesStaleMessage != null)
          _Banner(draft.pagesStaleMessage!),
        if (coverage.status == 'stale')
          _Banner(coverage.reason ?? '涵蓋檢查的結果可能過期'),
        if (coverage.status == 'not_done')
          _Banner('涵蓋檢查沒做成：${coverage.reason ?? '原因不明'}'),
        if (coverage.status != 'not_done') ...[
          _CoverageSummary(coverage: coverage),
          const SizedBox(height: AppSpacing.medium),
        ],
        Padding(
          key: const Key('video-check-count'),
          padding: const EdgeInsets.only(bottom: AppSpacing.medium),
          child: Text('已檢查 $checked／$total 句', style: text.titleSmall),
        ),
        for (final (i, segment) in draft.segments.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: _SegmentCard(
              projectId: projectId,
              index: i,
              segment: segment,
              checks: checks,
            ),
          ),
        if (draft.assets.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.small),
          Text('需要的素材', style: text.titleMedium),
          const SizedBox(height: AppSpacing.small),
          Card(
            child: Column(
              children: [
                for (final asset in draft.assets)
                  ListTile(
                    key: Key('video-asset-${asset.assetKey}'),
                    title: Text(asset.reason),
                    subtitle: asset.shot == null
                        ? null
                        : Text('拍攝說明：${asset.shot}'),
                    trailing: PillBadge(
                      label: asset.priority == 'required' ? '必拍' : '選拍',
                      tone: asset.priority == 'required'
                          ? PillTone.accent
                          : PillTone.neutral,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.medium),
    child: NoticeBanner(text: text),
  );
}

/// 涵蓋檢查摘要：幾項問題（警告色）、幾項提示（一般色）；細節展開才看。
class _CoverageSummary extends StatefulWidget {
  const _CoverageSummary({required this.coverage});

  final DraftCoverage coverage;

  @override
  State<_CoverageSummary> createState() => _CoverageSummaryState();
}

class _CoverageSummaryState extends State<_CoverageSummary> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final coverage = widget.coverage;
    final text = Theme.of(context).textTheme;
    final problems = coverage.issues.length + coverage.problems.length;
    final hints = coverage.hints.length;
    if (problems == 0 && hints == 0) {
      return Card(
        key: const Key('video-coverage-summary'),
        child: ListTile(
          leading: Icon(
            Icons.check_circle_outline,
            color: Theme.of(context).colorScheme.primary,
          ),
          title: const Text('涵蓋檢查沒有發現問題'),
        ),
      );
    }
    return Card(
      key: const Key('video-coverage-summary'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('涵蓋檢查', style: text.titleSmall),
                const SizedBox(width: AppSpacing.small),
                Expanded(
                  child: Wrap(
                    spacing: AppSpacing.small,
                    runSpacing: AppSpacing.xSmall,
                    children: [
                      if (problems > 0)
                        PillBadge(
                          label: '$problems 項問題',
                          tone: PillTone.accent,
                          icon: Icons.warning_amber_outlined,
                        ),
                      if (hints > 0)
                        PillBadge(
                          label: '$hints 項提示',
                          tone: PillTone.neutral,
                          icon: Icons.lightbulb_outline,
                        ),
                    ],
                  ),
                ),
                TextButton(
                  key: const Key('video-coverage-toggle'),
                  onPressed: () => setState(() => _expanded = !_expanded),
                  child: Text(_expanded ? '收起' : '看細節'),
                ),
              ],
            ),
            if (_expanded) ...[
              for (final issue in coverage.issues)
                _Detail(
                  title: issue.source,
                  lines: [
                    if (issue.narrationMissing != null)
                      '旁白缺少：${issue.narrationMissing}',
                    if (issue.subtitleMissing != null)
                      '字幕缺少：${issue.subtitleMissing}',
                  ],
                ),
              for (final problem in coverage.problems)
                _Detail(
                  title: '「${problem.text}」',
                  lines: [
                    '${problem.track == 'subtitle' ? '字幕' : '旁白'}：'
                        '${problem.reason}',
                  ],
                ),
              if (coverage.hints.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.small),
                Text('提示（目的說明）', style: text.labelLarge),
                for (final hint in coverage.hints)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.xSmall),
                    child: Text(hint.source, style: text.bodyMedium),
                  ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _Detail extends StatelessWidget {
  const _Detail({required this.title, required this.lines});

  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.small),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: text.bodyMedium),
          for (final line in lines)
            Text(
              line,
              style: text.bodySmall!.copyWith(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
        ],
      ),
    );
  }
}

class _SegmentCard extends ConsumerWidget {
  const _SegmentCard({
    required this.projectId,
    required this.index,
    required this.segment,
    required this.checks,
  });

  final String projectId;
  final int index;
  final DraftSegment segment;
  final Set<String> checks;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      key: Key('video-segment-${segment.segmentKey}'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text('第 ${index + 1} 段', style: text.titleMedium),
                ),
                // 出處頁：點下回到那一頁改文字
                Wrap(
                  spacing: AppSpacing.xSmall,
                  children: [
                    for (final page in segment.sourcePages)
                      ActionChip(
                        label: Text('p.$page'),
                        visualDensity: VisualDensity.compact,
                        onPressed: () =>
                            context.go('/videos/$projectId/pages?page=$page'),
                      ),
                  ],
                ),
              ],
            ),
            for (final beat in segment.beats)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.small),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Checkbox(
                      key: Key('video-beat-check-${beat.beatKey}'),
                      value: checks.contains(beat.beatKey),
                      onChanged: (_) => ref
                          .read(subtitleChecksProvider(projectId).notifier)
                          .toggle(beat.beatKey),
                    ),
                    const SizedBox(width: AppSpacing.small),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(beat.narration, style: text.bodyLarge),
                          const SizedBox(height: AppSpacing.xSmall),
                          DecoratedBox(
                            decoration: BoxDecoration(
                              color: scheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(
                                AppRadius.button,
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.small,
                                vertical: AppSpacing.xSmall,
                              ),
                              child: Text(
                                beat.subtitle,
                                style: text.bodySmall!.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
