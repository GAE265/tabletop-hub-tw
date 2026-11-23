import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_assets_state.dart';
import '../state/video_assets_summary.dart';
import '../state/video_draft_state.dart';
import '../state/video_projects_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 素材清單（`/videos/:id/assets`，Stitch 版面）：
///
/// - 步驟條（目前在「拍攝素材」）、專案卡（每格幾段、素材完成進度）、可以隨時離開的提示。
/// - 「還缺這些才能產生影片」：每個缺照片或區域的素材一張卡片，卡片上直接拍照、標區域或略過。
/// - 「已完成」：已拍好或略過的素材，點進去可以換照片或重標區域。
/// - 底部列：已略過幾個、目前完成幾 %、「下一步：產生影片」。
///
/// 每個素材標示可略過、代表牌、有沒有照片、區域標好了沒（design.md D14）。
/// 木紋背景；手機的浮動導覽列蓋住的高度留在底部列下面。
class VideoAssetsPage extends ConsumerWidget {
  const VideoAssetsPage({required this.projectId, super.key});

  final String projectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(videoDraftProvider(projectId));
    final readiness = ref.watch(videoReadinessProvider(projectId));
    final body = VideoPageBody(
      child: draft.when(
        skipLoadingOnRefresh: false,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: ThickCard(
              child: Padding(
                padding: _inset,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      error is ApiException ? error.message : '發生未知錯誤',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: AppSpacing.medium),
                    FilledButton(
                      onPressed: () {
                        ref
                          ..invalidate(videoDraftProvider(projectId))
                          ..invalidate(videoReadinessProvider(projectId));
                      },
                      child: const Text('重試'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        data: (value) => value == null
            ? Center(
                child: ThickCard(
                  child: Padding(
                    padding: _inset,
                    child: Text(
                      '還沒有草稿',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ),
              )
            : _Content(
                projectId: projectId,
                draft: value,
                readiness: readiness,
              ),
      ),
    );
    return Scaffold(
      key: const Key('video-assets-page'),
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('拍素材'),
        // 放在木紋上，用半透明白底，文字才看得清楚
        backgroundColor: AppColors.headerGlass,
      ),
      body: WoodBackground.isPaintedAbove(context)
          ? body
          : WoodBackground(child: body),
    );
  }
}

/// 有厚度卡片的標準內距。
const _inset = EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall);

class _Content extends ConsumerWidget {
  const _Content({
    required this.projectId,
    required this.draft,
    required this.readiness,
  });

  final String projectId;
  final VideoDraft draft;
  final AsyncValue<VideoReadiness> readiness;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final project = ref.watch(videoProjectProvider(projectId)).value;
    final r = readiness.value;
    final progress = assetsProgress(draft, r);
    final listState = ref.watch(videoAssetListProvider(projectId));
    final steps = videoSteps(rulebookPhotos: project?.rulebook == 'photos');
    final pending = r == null ? <String>[] : pendingAssetKeys(draft, r);
    final byKey = {for (final a in draft.assets) a.assetKey: a};
    final done = r == null
        ? const <DraftAsset>[]
        : [
            for (final a in draft.assets)
              if (!pending.contains(a.assetKey)) a,
          ];
    const gap = SizedBox(height: AppSpacing.medium);
    return Column(
      children: [
        Expanded(
          // 素材不多，一次建好（不用延遲建立的 ListView），捲到哪裡都找得到
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.medium),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ThickCard(
                  child: Padding(
                    padding: _inset,
                    child: VideoStepper(
                      steps: steps,
                      current: steps.indexWhere((s) => s.label == '拍攝素材'),
                    ),
                  ),
                ),
                gap,
                _ProjectCard(
                  project: project,
                  draft: draft,
                  progress: progress,
                ),
                gap,
                const _Tip(),
                const SizedBox(height: AppSpacing.large),
                if (listState.error case final error?) ...[
                  _ErrorBox(text: error),
                  gap,
                ],
                readiness.when(
                  skipLoadingOnRefresh: false,
                  loading: () => const LinearProgressIndicator(),
                  error: (error, _) => ThickCard(
                    child: Padding(
                      padding: _inset,
                      child: Text(
                        error is ApiException ? error.message : '讀不到還缺什麼',
                      ),
                    ),
                  ),
                  data: (r) => _Pending(
                    projectId: projectId,
                    readiness: r,
                    assets: [for (final key in pending) byKey[key]!],
                  ),
                ),
                if (done.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.large),
                  SectionBar(
                    key: const Key('video-assets-done-header'),
                    title: '已完成',
                    icon: Icons.check_circle_outline,
                    trailing: _Muted('${done.length} 項'),
                  ),
                  for (final a in done) ...[
                    gap,
                    _AssetCard(
                      projectId: projectId,
                      asset: a,
                      missingRegions: 0,
                    ),
                  ],
                ],
              ],
            ),
          ),
        ),
        _BottomBar(
          projectId: projectId,
          progress: progress,
          ready: r?.ready ?? false,
        ),
      ],
    );
  }
}

/// 專案卡：進行中與最後修改、專案名稱與桌遊、每格幾段、素材完成進度。
class _ProjectCard extends StatelessWidget {
  const _ProjectCard({
    required this.project,
    required this.draft,
    required this.progress,
  });

  final VideoProject? project;
  final VideoDraft draft;
  final VideoAssetsProgress progress;

  static String _two(int n) => n.toString().padLeft(2, '0');

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final p = project;
    final chapters = chapterSegmentCounts(draft);
    final muted = text.bodySmall!.copyWith(color: AppColors.inkMuted);
    return ThickCard(
      key: const Key('video-assets-project'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (p != null) ...[
              Row(
                children: [
                  PillBadge(
                    label: p.step == 'done' ? '已完成' : '進行中',
                    tone: p.step == 'done'
                        ? PillTone.players
                        : PillTone.duration,
                  ),
                  const SizedBox(width: AppSpacing.small),
                  Expanded(
                    child: Builder(
                      builder: (context) {
                        final t = p.updatedAt.toLocal();
                        return Text(
                          '最後修改：${t.month}/${t.day} '
                          '${_two(t.hour)}:${_two(t.minute)}',
                          style: muted,
                        );
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.small),
              Text(
                p.title,
                style: text.titleLarge!.copyWith(fontWeight: FontWeight.w700),
              ),
              Text('桌遊：${p.gameName}', style: muted),
              const SizedBox(height: AppSpacing.medium),
            ],
            if (chapters.isNotEmpty) ...[
              Row(
                key: const Key('video-assets-chapters'),
                children: [
                  for (final (i, (label, count)) in chapters.indexed) ...[
                    if (i > 0) const SizedBox(width: AppSpacing.small),
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          vertical: AppSpacing.small,
                          horizontal: AppSpacing.xSmall,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.backgroundAlt,
                          border: Border.all(color: AppColors.cardEdge),
                          borderRadius: BorderRadius.circular(AppRadius.button),
                        ),
                        child: Column(
                          children: [
                            Text(
                              label,
                              style: text.titleSmall!.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Text('$count 段', style: muted),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: AppSpacing.medium),
            ],
            Row(
              children: [
                Expanded(
                  child: Text(
                    '素材進度',
                    style: text.titleSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  '已完成 ${progress.done}／${progress.total} 個素材',
                  style: text.titleSmall!.copyWith(
                    color: AppColors.primaryText,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.pill),
              child: LinearProgressIndicator(
                value: progress.total == 0 ? 1 : progress.done / progress.total,
                minHeight: AppSpacing.small,
                color: AppColors.primary,
                backgroundColor: AppColors.neutralTint,
              ),
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '已略過 ${progress.skipped} 個・還缺 ${progress.pending} 個',
              style: muted,
            ),
          ],
        ),
      ),
    );
  }
}

/// 綠色提示：照片選好就上傳，隨時可以離開。
class _Tip extends StatelessWidget {
  const _Tip();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      key: const Key('video-assets-tip'),
      padding: const EdgeInsets.all(AppSpacing.medium),
      decoration: BoxDecoration(
        color: AppColors.sageTint,
        border: Border.all(color: AppColors.sage.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_done_outlined, color: AppColors.sage),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '拍攝中隨時可以離開這頁',
                  style: text.titleSmall!.copyWith(
                    color: AppColors.sage,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text('每張照片選好就會上傳，之後回來接著拍就好', style: text.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 還缺這些：全部齊了時是「可以產生影片」；否則標題條（剩幾項）、每個素材一張卡片、
/// 本版不支援的素材。
class _Pending extends StatelessWidget {
  const _Pending({
    required this.projectId,
    required this.readiness,
    required this.assets,
  });

  final String projectId;
  final VideoReadiness readiness;
  final List<DraftAsset> assets;

  @override
  Widget build(BuildContext context) {
    if (readiness.ready) {
      return const ThickCard(
        key: Key('video-readiness'),
        child: ListTile(
          leading: Icon(Icons.check_circle, color: AppColors.sage),
          title: Text('可以產生影片'),
        ),
      );
    }
    final photos = {for (final p in readiness.missingPhotos) p.assetKey: p};
    return Column(
      key: const Key('video-readiness'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionBar(
          key: const Key('video-assets-pending-header'),
          title: '還缺這些才能產生影片',
          trailing: _Muted('剩 ${assets.length} 項'),
        ),
        for (final (i, a) in assets.indexed) ...[
          const SizedBox(height: AppSpacing.medium),
          _AssetCard(
            projectId: projectId,
            asset: a,
            number: i + 1,
            missingPhoto: photos[a.assetKey],
            missingRegionNames: [
              for (final m in readiness.missingRegions)
                if (m.assetKey == a.assetKey) m.region,
            ],
            missingRegions: readiness.missingRegions
                .where((m) => m.assetKey == a.assetKey)
                .length,
          ),
        ],
        for (final u in readiness.unsupported) ...[
          const SizedBox(height: AppSpacing.medium),
          _ErrorBox(text: u.message),
        ],
      ],
    );
  }
}

/// 一個素材的卡片；點整張進到素材頁。
///
/// 還缺的素材（有 [number]）：編號、為什麼要拍、拍攝說明、還沒標的區域、略過會影響哪幾段，
/// 下方是「拍照或選圖」或「標區域」，可以略過時加「略過這個素材」（先確認）。
class _AssetCard extends ConsumerWidget {
  const _AssetCard({
    required this.projectId,
    required this.asset,
    required this.missingRegions,
    this.number,
    this.missingPhoto,
    this.missingRegionNames = const [],
  });

  final String projectId;
  final DraftAsset asset;

  /// 這個素材還沒標的區域數。
  final int missingRegions;

  /// 還缺這些裡的第幾項；已完成的素材是 null。
  final int? number;
  final MissingPhoto? missingPhoto;
  final List<String> missingRegionNames;

  Future<void> _skip(BuildContext context, WidgetRef ref) async {
    final affected = missingPhoto?.skipAffectedSegments ?? const [];
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('略過這個素材？'),
        content: Text(
          '影片不會用到「${assetDisplayName(asset)}」的照片。'
          '${affected.isEmpty ? '' : '第 ${affected.join('、')} 段的畫面會跟著調整。'}',
        ),
        actions: [
          TextButton(
            key: const Key('video-asset-skip-cancel'),
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            key: const Key('video-asset-skip-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('略過'),
          ),
        ],
      ),
    );
    if (ok ?? false) {
      await ref
          .read(videoAssetListProvider(projectId).notifier)
          .skip(asset.assetKey);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(color: AppColors.inkMuted);
    final key = asset.assetKey;
    final base = '/videos/$projectId/assets/$key';
    final total = asset.regions.length;
    final pending = number != null;
    final needsPhoto = missingPhoto != null;
    final skippable =
        needsPhoto &&
        !asset.skipped &&
        (missingPhoto!.skippable || asset.skippable);
    final affected = missingPhoto?.skipAffectedSegments ?? const <int>[];
    final busy = ref.watch(videoAssetListProvider(projectId)).busyKey == key;
    return ThickCard(
      key: Key('video-asset-tile-$key'),
      onTap: () => context.go(base),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (number case final n?) ...[
                  CircleAvatar(
                    radius: AppSizes.stepDot / 2 - AppSpacing.xSmall,
                    backgroundColor: AppColors.primaryTint,
                    foregroundColor: AppColors.primaryText,
                    child: Text(
                      '$n',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                ] else ...[
                  Icon(
                    asset.skipped ? Icons.block : Icons.check_circle,
                    color: asset.skipped ? AppColors.inkMuted : AppColors.sage,
                  ),
                  const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                ],
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        assetDisplayName(asset),
                        style: text.titleMedium!.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xSmall),
                      _Badges(
                        asset: asset,
                        total: total,
                        missingRegions: missingRegions,
                      ),
                    ],
                  ),
                ),
                if (!pending)
                  const Icon(Icons.chevron_right, color: AppColors.inkMuted),
              ],
            ),
            if (pending) ...[
              const SizedBox(height: AppSpacing.small),
              if (asset.reason.isNotEmpty)
                Text('為什麼要拍：${asset.reason}', style: text.bodyMedium),
              if (asset.shot case final shot?) ...[
                const SizedBox(height: AppSpacing.xSmall),
                Text('拍攝說明：$shot', style: muted),
              ],
              if (missingRegionNames.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.xSmall),
                Text(
                  '待標區域：${missingRegionNames.join('、')}',
                  style: text.bodySmall!.copyWith(color: AppColors.amberText),
                ),
              ],
              if (skippable && affected.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.xSmall),
                Text(
                  '略過會影響第 ${affected.join('、')} 段',
                  style: text.bodySmall!.copyWith(color: AppColors.amberText),
                ),
              ],
              const SizedBox(height: AppSpacing.medium),
              Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small,
                children: [
                  if (needsPhoto)
                    ThickButton(
                      buttonKey: Key('video-asset-shoot-$key'),
                      style: ThickStyle.primary,
                      icon: Icons.photo_camera_outlined,
                      label: '拍照或選圖',
                      shadow: AppShadows.soft,
                      onPressed: () => context.go(base),
                    )
                  else if (missingRegionNames.isNotEmpty)
                    ThickButton(
                      buttonKey: Key('video-asset-regions-$key'),
                      style: ThickStyle.dark,
                      icon: Icons.crop_free,
                      label: '標區域',
                      shadow: AppShadows.soft,
                      onPressed: () => context.go('$base/regions'),
                    ),
                  if (skippable)
                    ThickButton(
                      buttonKey: Key('video-asset-skip-$key'),
                      style: ThickStyle.light,
                      icon: Icons.block,
                      label: '略過這個素材',
                      shadow: AppShadows.soft,
                      onPressed: busy ? null : () => _skip(context, ref),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 素材的標籤：可略過（程式判斷，不看 AI 標的 priority）、代表牌、已拍／未拍／已略過、區域。
class _Badges extends StatelessWidget {
  const _Badges({
    required this.asset,
    required this.total,
    required this.missingRegions,
  });

  final DraftAsset asset;
  final int total;
  final int missingRegions;

  @override
  Widget build(BuildContext context) {
    final missing = missingRegions;
    return Wrap(
      spacing: AppSpacing.small,
      runSpacing: AppSpacing.xSmall,
      children: [
        // 程式判斷的「可略過」（2026-11-22 永傑決定，不看 AI 標的 priority）
        if (asset.skippable && !asset.skipped)
          const PillBadge(label: '可略過', tone: PillTone.neutral),
        if (asset.representative)
          const PillBadge(label: '代表牌', tone: PillTone.neutral),
        if (asset.skipped)
          const PillBadge(
            label: '已略過',
            tone: PillTone.neutral,
            icon: Icons.block,
          )
        else
          PillBadge(
            label: asset.hasPhoto ? '已拍' : '未拍',
            tone: asset.hasPhoto ? PillTone.players : PillTone.duration,
            icon: asset.hasPhoto ? Icons.check : Icons.photo_camera_outlined,
          ),
        if (total > 0 && !asset.skipped)
          PillBadge(
            label: missing == 0 ? '區域已標好' : '區域 ${total - missing}／$total',
            tone: missing == 0 ? PillTone.players : PillTone.duration,
          ),
      ],
    );
  }
}

/// 底部列：已略過幾個、目前完成幾 %，右邊「下一步：產生影片」（全部齊了才能按）。
class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.projectId,
    required this.progress,
    required this.ready,
  });

  final String projectId;
  final VideoAssetsProgress progress;
  final bool ready;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    // 手機的浮動導覽列蓋住的高度
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        0,
        AppSpacing.medium,
        AppSpacing.medium + bottomInset,
      ),
      child: ThickCard(
        key: const Key('video-assets-bar'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '已略過 ${progress.skipped} 個素材',
                      style: text.bodySmall!.copyWith(
                        color: AppColors.inkMuted,
                      ),
                    ),
                    Text(
                      '目前完成 ${progress.percent}%',
                      style: text.titleSmall!.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.small),
              ThickButton(
                buttonKey: const Key('video-assets-next'),
                style: ThickStyle.primary,
                icon: Icons.arrow_forward,
                label: '下一步：產生影片',
                onPressed: ready
                    ? () => context.go('/videos/$projectId/render')
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 標題條右邊的灰字。
class _Muted extends StatelessWidget {
  const _Muted(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: Theme.of(
      context,
    ).textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
  );
}

/// 紅色的錯誤或警告（略過失敗、本版不支援的素材）。
class _ErrorBox extends StatelessWidget {
  const _ErrorBox({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(AppSpacing.medium),
    decoration: BoxDecoration(
      color: AppColors.errorTint,
      border: Border.all(color: AppColors.errorEdge),
      borderRadius: BorderRadius.circular(AppRadius.button),
    ),
    child: Row(
      children: [
        const Icon(Icons.error_outline, color: AppColors.error),
        const SizedBox(width: AppSpacing.small),
        Expanded(
          child: Text(text, style: const TextStyle(color: AppColors.error)),
        ),
      ],
    ),
  );
}
