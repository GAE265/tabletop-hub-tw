import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../data/video_image_size.dart';
import '../data/video_studio_models.dart';
import '../state/video_assets_state.dart';
import '../state/video_render_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 單一素材（`/videos/:id/assets/:key`，外觀決定）：拍攝說明在上方；照片右上角旋轉；
/// 拍照按鈕在下方中央；看原圖；換照片後提示重新確認區域。
class VideoAssetPage extends ConsumerStatefulWidget {
  const VideoAssetPage({
    required this.projectId,
    required this.assetKey,
    super.key,
  });

  final String projectId;
  final String assetKey;

  @override
  ConsumerState<VideoAssetPage> createState() => _VideoAssetPageState();
}

class _VideoAssetPageState extends ConsumerState<VideoAssetPage> {
  VideoAssetRef get _ref =>
      (projectId: widget.projectId, assetKey: widget.assetKey);

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) ref.read(videoAssetProvider(_ref).notifier).load();
    });
  }

  void _showFull(BuildContext context, VideoAssetState state) {
    showDialog<void>(
      context: context,
      builder: (context) => Dialog.fullscreen(
        key: const Key('video-asset-full-photo'),
        child: Stack(
          children: [
            Positioned.fill(
              child: InteractiveViewer(
                child: Center(
                  child: RotatedBox(
                    quarterTurns: state.asset!.orientation ~/ 90,
                    child: Image.memory(state.photo!),
                  ),
                ),
              ),
            ),
            Positioned(
              top: AppSpacing.small,
              right: AppSpacing.small,
              child: SafeArea(
                child: IconButton.filledTonal(
                  tooltip: '關閉',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 略過前先說明會影響哪幾段（2026-11-22 永傑決定）。
  Future<void> _confirmSkip(BuildContext context, VideoAsset asset) async {
    final affected = asset.skipAffectedSegments;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('略過這張選拍素材？'),
        content: Text(
          affected.isEmpty ? '沒有段用到這張素材' : skipConfirmText(affected),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('略過'),
          ),
        ],
      ),
    );
    if ((ok ?? false) && mounted) {
      await ref.read(videoAssetProvider(_ref).notifier).setSkipped(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoAssetProvider(_ref));
    final notifier = ref.read(videoAssetProvider(_ref).notifier);
    final asset = state.asset;
    final photo = state.photo;
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final hasRegions = asset != null && asset.regions.isNotEmpty;
    final size = photo == null ? null : imageSizeOf(photo);
    return Scaffold(
      key: const Key('video-asset-page'),
      appBar: AppBar(title: const Text('素材')),
      bottomNavigationBar: asset == null
          ? null
          : VideoBottomActions(
              children: [
                FilledButton.icon(
                  key: const Key('video-asset-pick'),
                  onPressed: state.busy ? null : notifier.pickAndUpload,
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: Text(asset.hasPhoto ? '重拍或換一張' : '拍照或選圖'),
                ),
              ],
            ),
      body: VideoPageBody(
        child: asset == null
            ? (state.error != null
                  ? Padding(
                      padding: const EdgeInsets.all(AppSpacing.medium),
                      child: NoticeBanner(text: state.error!, isError: true),
                    )
                  : const Center(child: CircularProgressIndicator()))
            : ListView(
                padding: const EdgeInsets.all(AppSpacing.medium),
                children: [
                  Card(
                    key: const Key('video-asset-shot'),
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.medium),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('拍攝說明', style: text.labelLarge),
                          const SizedBox(height: AppSpacing.xSmall),
                          Text(
                            asset.shot ?? asset.reason,
                            style: text.titleMedium,
                          ),
                          if (asset.shot != null) ...[
                            const SizedBox(height: AppSpacing.xSmall),
                            Text(asset.reason, style: text.bodySmall),
                          ],
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.medium),
                  if (asset.priority == 'optional') ...[
                    _SkipSection(
                      asset: asset,
                      busy: state.busy,
                      onSkip: () => _confirmSkip(context, asset),
                      onUnskip: () => notifier.setSkipped(false),
                    ),
                    const SizedBox(height: AppSpacing.medium),
                  ],
                  if (state.error != null) ...[
                    NoticeBanner(text: state.error!, isError: true),
                    const SizedBox(height: AppSpacing.medium),
                  ],
                  if (state.photoReplaced) ...[
                    const NoticeBanner(text: '換了照片，請重新確認區域'),
                    const SizedBox(height: AppSpacing.medium),
                  ],
                  if (state.busy) ...[
                    const LinearProgressIndicator(),
                    const SizedBox(height: AppSpacing.small),
                  ],
                  if (photo == null)
                    Card(
                      color: scheme.surfaceContainerHighest,
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.xLarge),
                        child: Column(
                          children: [
                            Icon(
                              Icons.image_outlined,
                              size: AppSizes.emptyStateIcon,
                              color: scheme.onSurfaceVariant,
                            ),
                            const Text('還沒有照片'),
                          ],
                        ),
                      ),
                    )
                  else
                    Stack(
                      key: const Key('video-asset-photo'),
                      children: [
                        GestureDetector(
                          onTap: () => _showFull(context, state),
                          child: AspectRatio(
                            aspectRatio: size == null
                                ? 4 / 3
                                : displaySize(
                                    size,
                                    asset.orientation,
                                  ).aspectRatio,
                            child: RotatedBox(
                              quarterTurns: asset.orientation ~/ 90,
                              child: Image.memory(photo, fit: BoxFit.fill),
                            ),
                          ),
                        ),
                        Positioned(
                          top: AppSpacing.small,
                          right: AppSpacing.small,
                          child: IconButton.filledTonal(
                            key: const Key('video-asset-rotate'),
                            tooltip: '旋轉',
                            onPressed: state.busy ? null : notifier.rotate,
                            icon: const Icon(Icons.rotate_right),
                          ),
                        ),
                      ],
                    ),
                  if (photo != null) ...[
                    const SizedBox(height: AppSpacing.small),
                    Row(
                      children: [
                        TextButton.icon(
                          onPressed: () => _showFull(context, state),
                          icon: const Icon(Icons.zoom_in),
                          label: const Text('看原圖'),
                        ),
                        const Spacer(),
                        if (hasRegions)
                          OutlinedButton.icon(
                            key: const Key('video-asset-regions'),
                            onPressed: () => context.go(
                              '/videos/${widget.projectId}/assets/'
                              '${widget.assetKey}/regions',
                            ),
                            icon: const Icon(Icons.crop_free),
                            label: Text(
                              '標區域（${asset.regions.values.where((b) => b != null).length}'
                              '／${asset.regions.length}）',
                            ),
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

/// 選拍素材的略過：可以略過、已略過（可取消）、只靠它的段不能略過。
class _SkipSection extends StatelessWidget {
  const _SkipSection({
    required this.asset,
    required this.busy,
    required this.onSkip,
    required this.onUnskip,
  });

  final VideoAsset asset;
  final bool busy;
  final VoidCallback onSkip;
  final VoidCallback onUnskip;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    if (asset.skipped) {
      return Card(
        child: ListTile(
          leading: const Icon(Icons.block),
          title: const Text('已略過'),
          subtitle: const Text('產生影片時不用這張'),
          trailing: OutlinedButton(
            key: const Key('video-asset-unskip'),
            onPressed: busy ? null : onUnskip,
            child: const Text('取消略過'),
          ),
        ),
      );
    }
    if (asset.skipBlockedSegments.isNotEmpty) {
      return Text(
        skipBlockedText(asset.skipBlockedSegments),
        style: text.bodyMedium,
      );
    }
    return Align(
      alignment: Alignment.centerLeft,
      child: OutlinedButton.icon(
        key: const Key('video-asset-skip'),
        onPressed: busy ? null : onSkip,
        icon: const Icon(Icons.block),
        label: const Text('略過這張'),
      ),
    );
  }
}
