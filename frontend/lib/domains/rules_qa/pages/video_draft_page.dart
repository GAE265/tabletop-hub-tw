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

/// 草稿（`/videos/:id/draft`，design.md D17）：只顯示進度與結果摘要，不擋流程。
/// 摘要是三格各幾段幾句、必拍與選拍各幾個，以及依格的涵蓋檢查（細節展開才看）。
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
    final jobCard = VideoJobCard(projectId: _id, showDone: false);
    return Scaffold(
      key: const Key('video-draft-page'),
      appBar: AppBar(title: const Text('草稿')),
      bottomNavigationBar: draft.value == null
          ? null
          : VideoBottomActions(
              children: [
                OutlinedButton(
                  key: const Key('video-draft-regenerate'),
                  onPressed: running ? null : _regenerate,
                  child: const Text('重新產生'),
                ),
                // 不擋流程：涵蓋檢查有問題也可以往下（漏講的之後用修改補救）
                FilledButton(
                  key: const Key('video-draft-next'),
                  onPressed: () => context.go('/videos/$_id/assets'),
                  child: const Text('下一步：拍素材'),
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
                    const SizedBox(height: AppSpacing.small),
                    Text(
                      '建立專案後會自動產生；正在產生時上方會顯示進度',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: AppSpacing.medium),
                    if (!running)
                      FilledButton(
                        onPressed: _regenerate,
                        child: const Text('產生草稿'),
                      ),
                  ],
                )
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.medium),
                  children: [
                    jobCard,
                    ..._banners(value),
                    _Summary(draft: value),
                    const SizedBox(height: AppSpacing.medium),
                    _CoverageBySlot(coverage: value.coverage),
                  ],
                ),
        ),
      ),
    );
  }

  List<Widget> _banners(VideoDraft draft) {
    final coverage = draft.coverage;
    return [
      if (draft.terms.status == 'missing' && draft.terms.message != null)
        _Banner(draft.terms.message!),
      if (coverage.status == 'stale') _Banner(coverage.reason ?? '涵蓋檢查的結果可能過期'),
      if (coverage.status == 'not_done' && coverage.slots.isEmpty)
        _Banner('涵蓋檢查沒做成：${coverage.reason ?? '原因不明'}'),
    ];
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

/// 結果摘要：三格各幾段幾句、必拍與選拍各幾個。
class _Summary extends StatelessWidget {
  const _Summary({required this.draft});

  final VideoDraft draft;

  @override
  Widget build(BuildContext context) {
    final summary = draftSummary(draft);
    final text = Theme.of(context).textTheme;
    return Card(
      key: const Key('video-draft-summary'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('草稿內容', style: text.titleSmall),
            const SizedBox(height: AppSpacing.small),
            for (final slot in summary.slots)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xSmall),
                child: Text(
                  '${slot.title}：${slot.segments} 段、${slot.beats} 句',
                  style: text.bodyMedium,
                ),
              ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '素材：必拍 ${summary.mustAssets}、選拍 ${summary.optionalAssets}',
              style: text.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

/// 涵蓋檢查依格的摘要（幾項問題、幾項提示）；細節展開才看。提示，不擋下。
class _CoverageBySlot extends StatefulWidget {
  const _CoverageBySlot({required this.coverage});

  final DraftCoverage coverage;

  @override
  State<_CoverageBySlot> createState() => _CoverageBySlotState();
}

class _CoverageBySlotState extends State<_CoverageBySlot> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final coverage = widget.coverage;
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    // 舊的單章草稿沒有依格的摘要：當成一格
    final slots = coverage.slots.isNotEmpty
        ? coverage.slots
        : [
            CoverageSlot(
              slot: '',
              title: '全部',
              status: coverage.status == 'not_done' ? 'not_done' : 'done',
              reason: coverage.reason,
              totalRules: coverage.totalRules,
              issues: coverage.issues,
              problems: coverage.problems,
              hints: coverage.hints,
            ),
          ];
    final hasDetails = slots.any(
      (s) => s.issues.isNotEmpty || s.problems.isNotEmpty || s.hints.isNotEmpty,
    );
    return Card(
      key: const Key('video-coverage-summary'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text('涵蓋檢查', style: text.titleSmall)),
                if (hasDetails)
                  TextButton(
                    key: const Key('video-coverage-toggle'),
                    onPressed: () => setState(() => _expanded = !_expanded),
                    child: Text(_expanded ? '收起' : '看細節'),
                  ),
              ],
            ),
            for (final slot in slots) ...[
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xSmall),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(_slotLine(slot), style: text.bodyMedium),
                    ),
                    if (slot.issues.isNotEmpty || slot.problems.isNotEmpty)
                      const PillBadge(label: '要看', tone: PillTone.accent),
                  ],
                ),
              ),
              if (_expanded) ...[
                for (final issue in slot.issues)
                  _Detail(
                    title: issue.source,
                    lines: [
                      if (issue.narrationMissing != null)
                        '旁白缺少：${issue.narrationMissing}',
                      if (issue.subtitleMissing != null)
                        '字幕缺少：${issue.subtitleMissing}',
                    ],
                    color: scheme.error,
                  ),
                for (final problem in slot.problems)
                  _Detail(
                    title: '「${problem.text}」',
                    lines: [problem.reason],
                    color: scheme.error,
                  ),
                for (final hint in slot.hints)
                  _Detail(
                    title: hint.source,
                    lines: const [],
                    color: scheme.onSurfaceVariant,
                  ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  static String _slotLine(CoverageSlot slot) {
    if (slot.status != 'done') {
      return '${slot.title}：${slot.reason ?? '涵蓋檢查沒有完成'}';
    }
    final problems = slot.issues.length + slot.problems.length;
    final hints = slot.hints.length;
    if (problems == 0 && hints == 0) return '${slot.title}：沒有發現問題';
    final parts = [
      if (problems > 0) '$problems 項問題',
      if (hints > 0) '$hints 項提示',
    ];
    return '${slot.title}：${parts.join('、')}';
  }
}

class _Detail extends StatelessWidget {
  const _Detail({
    required this.title,
    required this.lines,
    required this.color,
  });

  final String title;
  final List<String> lines;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(
        top: AppSpacing.small,
        left: AppSpacing.medium,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: text.bodyMedium),
          for (final line in lines)
            Text(line, style: text.bodySmall!.copyWith(color: color)),
        ],
      ),
    );
  }
}
