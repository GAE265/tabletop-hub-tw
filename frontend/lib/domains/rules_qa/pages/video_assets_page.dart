import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_assets_state.dart';
import '../state/video_draft_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 素材清單（`/videos/:id/assets`）：最上方是還缺什麼；每個素材的必拍／選拍、代表牌、
/// 有沒有照片、區域標好了沒（design.md D14）。
class VideoAssetsPage extends ConsumerWidget {
  const VideoAssetsPage({required this.projectId, super.key});

  final String projectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(videoDraftProvider(projectId));
    final readiness = ref.watch(videoReadinessProvider(projectId));
    return Scaffold(
      key: const Key('video-assets-page'),
      appBar: AppBar(title: const Text('拍素材')),
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
          data: (value) => value == null
              ? Center(
                  child: Text(
                    '還沒有草稿',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.medium),
                  children: [
                    readiness.when(
                      loading: () => const LinearProgressIndicator(),
                      error: (error, _) => Text(
                        error is ApiException ? error.message : '讀不到還缺什麼',
                      ),
                      data: (r) => _ReadinessCard(readiness: r),
                    ),
                    const SizedBox(height: AppSpacing.medium),
                    for (final asset in value.assets)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: AppSpacing.small,
                        ),
                        child: _AssetTile(
                          projectId: projectId,
                          asset: asset,
                          missingRegions: readiness.value?.missingRegions
                              .where((m) => m.assetKey == asset.assetKey)
                              .length,
                        ),
                      ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _ReadinessCard extends StatelessWidget {
  const _ReadinessCard({required this.readiness});

  final VideoReadiness readiness;

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
                '拍照：${photo.reason}（${photo.priority == 'must' ? '必拍' : '選拍'}）',
                style: text.bodyMedium,
              ),
            for (final region in readiness.missingRegions)
              Text(
                '標區域：${region.assetKey} 的 ${region.region}',
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

class _AssetTile extends StatelessWidget {
  const _AssetTile({
    required this.projectId,
    required this.asset,
    required this.missingRegions,
  });

  final String projectId;
  final DraftAsset asset;

  /// 這個素材還沒標的區域數；readiness 還沒讀到時是 null。
  final int? missingRegions;

  @override
  Widget build(BuildContext context) {
    final total = asset.regions.length;
    final missing = missingRegions;
    return Card(
      key: Key('video-asset-tile-${asset.assetKey}'),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go('/videos/$projectId/assets/${asset.assetKey}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      asset.reason,
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    if (asset.shot != null) ...[
                      const SizedBox(height: AppSpacing.xSmall),
                      Text(
                        '拍攝說明：${asset.shot}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                    const SizedBox(height: AppSpacing.small),
                    Wrap(
                      spacing: AppSpacing.small,
                      runSpacing: AppSpacing.xSmall,
                      children: [
                        PillBadge(
                          label: asset.priority == 'must' ? '必拍' : '選拍',
                          tone: asset.priority == 'must'
                              ? PillTone.accent
                              : PillTone.neutral,
                        ),
                        if (asset.representative)
                          const PillBadge(label: '代表牌', tone: PillTone.neutral),
                        PillBadge(
                          label: asset.hasPhoto ? '已拍' : '未拍',
                          tone: asset.hasPhoto
                              ? PillTone.players
                              : PillTone.duration,
                          icon: asset.hasPhoto
                              ? Icons.check
                              : Icons.photo_camera_outlined,
                        ),
                        if (total > 0 && missing != null)
                          PillBadge(
                            label: missing == 0
                                ? '區域已標好'
                                : '區域 ${total - missing}／$total',
                            tone: missing == 0
                                ? PillTone.players
                                : PillTone.duration,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
