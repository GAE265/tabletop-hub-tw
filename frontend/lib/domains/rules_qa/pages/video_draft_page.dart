import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_draft_state.dart';
import '../state/video_job_state.dart';
import '../state/video_segment_swap_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 草稿（`/videos/:id/draft`，design.md D17）：只顯示進度與結果摘要，不擋流程。
/// 摘要是三格各幾段幾句、素材幾個與其中可略過幾個，以及依格的涵蓋檢查（細節展開才看）。
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

  /// 有已標好的區域時先確認：新草稿的區域名稱常常會變，標好的區域多半要重標（D17）。
  Future<void> _confirmRegenerate(VideoDraft draft) async {
    final marked = draft.assets.fold(0, (n, a) => n + a.markedRegions.length);
    if (marked == 0) {
      _regenerate();
      return;
    }
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('重新產生草稿？'),
        content: Text('已標的區域會要重標（目前已標 $marked 個）。照片會盡量沿用。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            key: const Key('video-draft-regenerate-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('重新產生'),
          ),
        ],
      ),
    );
    if ((ok ?? false) && mounted) _regenerate();
  }

  @override
  Widget build(BuildContext context) {
    final draft = ref.watch(videoDraftProvider(_id));
    final running = ref.watch(videoJobProvider(_id)).running;
    final jobCard = VideoJobCard(projectId: _id, showDone: false);
    return VideoScaffold(
      key: const Key('video-draft-page'),
      title: '草稿',
      bottom: draft.value == null
          ? null
          : VideoBottomActions(
              children: [
                ThickButton(
                  buttonKey: const Key('video-draft-regenerate'),
                  style: ThickStyle.light,
                  expand: true,
                  icon: Icons.refresh,
                  label: '重新產生',
                  shadow: AppShadows.soft,
                  onPressed: running
                      ? null
                      : () => _confirmRegenerate(draft.value!),
                ),
                // 不擋流程：涵蓋檢查有問題也可以往下（漏講的之後用修改補救）
                ThickButton(
                  buttonKey: const Key('video-draft-next'),
                  style: ThickStyle.primary,
                  expand: true,
                  label: '下一步：拍素材',
                  shadow: AppShadows.soft,
                  onPressed: () => context.go('/videos/$_id/assets'),
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
              child: ThickCard(
                child: Padding(
                  padding: videoCardInset,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        error is ApiException ? error.message : '發生未知錯誤',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: AppSpacing.medium),
                      ThickButton(
                        style: ThickStyle.primary,
                        label: '重試',
                        shadow: AppShadows.soft,
                        onPressed: () =>
                            ref.invalidate(videoDraftProvider(_id)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          data: (value) => value == null
              ? ListView(
                  padding: const EdgeInsets.all(AppSpacing.medium),
                  children: [
                    jobCard,
                    ThickCard(
                      child: Padding(
                        padding: videoCardInset,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
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
                            if (!running) ...[
                              const SizedBox(height: AppSpacing.medium),
                              ThickButton(
                                style: ThickStyle.primary,
                                expand: true,
                                icon: Icons.auto_awesome,
                                label: '產生草稿',
                                onPressed: _regenerate,
                              ),
                            ],
                          ],
                        ),
                      ),
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
                    if (value.segments.any((s) => s.slots.isNotEmpty)) ...[
                      const SizedBox(height: AppSpacing.medium),
                      _SegmentAssets(projectId: _id, draft: value),
                    ],
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

/// 每段的素材（換素材，2026-11-25 永傑決定，最小版）：每段列出格子用了哪個素材；
/// 單一素材的格子可以換成清單裡的另一個素材，放好幾張牌的格子寫明不支援。
class _SegmentAssets extends ConsumerWidget {
  const _SegmentAssets({required this.projectId, required this.draft});

  final String projectId;
  final VideoDraft draft;

  Future<void> _pick(
    BuildContext context,
    WidgetRef ref,
    DraftSegment segment,
    DraftSlot slot,
  ) async {
    final candidates = swapCandidates(draft, slot);
    final picked = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: Text('${slotDisplayName(slot.slot)}換成哪個素材？'),
        children: [
          if (candidates.isEmpty)
            const Padding(
              padding: EdgeInsets.all(AppSpacing.medium),
              child: Text('沒有其他可以換的素材'),
            ),
          for (final a in candidates)
            SimpleDialogOption(
              key: Key('video-swap-option-${a.assetKey}'),
              onPressed: () => Navigator.of(context).pop(a.assetKey),
              child: Text(assetDisplayName(a)),
            ),
        ],
      ),
    );
    if (picked == null || !context.mounted) return;
    await ref
        .read(videoSegmentSwapProvider(projectId).notifier)
        .swap(
          draft: draft,
          segmentKey: segment.segmentKey,
          slot: slot,
          assetKey: picked,
        );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(videoSegmentSwapProvider(projectId));
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    final names = {
      for (final a in draft.assets) a.assetKey: assetDisplayName(a),
    };
    return ThickCard(
      key: const Key('video-draft-segment-assets'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('每段的素材', style: text.titleMedium),
            Text('AI 指定錯素材時，可以換成清單裡的另一個素材', style: muted),
            if (state.notice case final notice?) ...[
              const SizedBox(height: AppSpacing.small),
              NoticeBanner(key: const Key('video-swap-notice'), text: notice),
              // 換素材不會自動更新影片（已經完成的專案也一樣），提醒店員重新產生
              const SizedBox(height: AppSpacing.small),
              Text('影片要重新產生才會用新的素材', style: muted),
              const SizedBox(height: AppSpacing.xSmall),
              ThickButton(
                buttonKey: const Key('video-swap-go-render'),
                style: ThickStyle.primary,
                expand: true,
                icon: Icons.movie_outlined,
                label: '前往產生影片',
                onPressed: () => context.go('/videos/$projectId/render'),
              ),
            ],
            if (state.error case final error?) ...[
              const SizedBox(height: AppSpacing.small),
              NoticeBanner(
                key: const Key('video-swap-error'),
                text: error,
                isError: true,
              ),
            ],
            for (final (i, segment) in draft.segments.indexed)
              if (segment.slots.isNotEmpty) ...[
                const Divider(height: AppSpacing.large),
                Text(
                  [
                    '第 ${i + 1} 段',
                    if (segment.beats.isNotEmpty) segment.beats.first.narration,
                  ].join('　'),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: text.bodyMedium!.copyWith(fontWeight: FontWeight.w600),
                ),
                for (final slot in segment.slots) ...[
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${slotDisplayName(slot.slot)}：'
                          '${slot.assetKeys.map((k) => names[k] ?? k).join('、')}',
                          key: Key(
                            'video-segment-${segment.segmentKey}-${slot.slot}',
                          ),
                        ),
                      ),
                      if (slot.swappable)
                        TextButton(
                          key: Key(
                            'video-segment-${segment.segmentKey}-${slot.slot}-swap',
                          ),
                          onPressed: state.busy
                              ? null
                              : () => _pick(context, ref, segment, slot),
                          child: const Text('換素材'),
                        ),
                    ],
                  ),
                  if (!slot.swappable)
                    Text(
                      '這一段目前不支援換素材',
                      key: Key(
                        'video-segment-${segment.segmentKey}-${slot.slot}-unsupported',
                      ),
                      style: muted,
                    ),
                ],
              ],
          ],
        ),
      ),
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

/// 結果摘要：三格各幾段幾句、素材幾個與其中可略過幾個。
class _Summary extends StatelessWidget {
  const _Summary({required this.draft});

  final VideoDraft draft;

  @override
  Widget build(BuildContext context) {
    final summary = draftSummary(draft);
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('video-draft-summary'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '草稿內容',
              style: text.titleMedium!.copyWith(fontWeight: FontWeight.w700),
            ),
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
              '素材：${summary.assets} 個，其中可略過 ${summary.skippableAssets} 個',
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
    return ThickCard(
      key: const Key('video-coverage-summary'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '涵蓋檢查',
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
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
