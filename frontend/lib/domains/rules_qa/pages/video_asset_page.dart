import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
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
    final blocked = asset.skipBlockedSegments;
    // 只靠它的段：改用文字卡（拍不了的素材不能擋住產生影片）
    final card = !asset.skippable && blocked.isNotEmpty;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(card ? '拍不了這個素材？' : '略過這張素材？'),
        content: Text(
          card
              ? textCardConfirmText(blocked, asset.label ?? asset.reason)
              : affected.isEmpty
              ? '沒有段用到這張素材'
              : skipConfirmText(affected),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(card ? '改用文字卡' : '略過'),
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
    return VideoScaffold(
      key: const Key('video-asset-page'),
      title: asset?.label ?? '素材',
      bottom: asset == null
          ? null
          : VideoBottomActions(
              children: [
                ThickButton(
                  buttonKey: const Key('video-asset-pick'),
                  style: ThickStyle.primary,
                  expand: true,
                  icon: Icons.photo_camera_outlined,
                  label: asset.hasPhoto ? '重拍或換一張' : '拍照或選圖',
                  shadow: AppShadows.soft,
                  onPressed: state.busy ? null : notifier.pickAndUpload,
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
                  ThickCard(
                    key: const Key('video-asset-shot'),
                    child: Padding(
                      padding: videoCardInset,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '拍攝說明',
                            style: text.labelLarge!.copyWith(
                              color: AppColors.primaryText,
                            ),
                          ),
                          const SizedBox(height: AppSpacing.xSmall),
                          Text(
                            asset.shot ?? asset.reason,
                            style: text.titleMedium!.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
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
                  if (asset.skipped ||
                      asset.skippable ||
                      asset.skipBlockedSegments.isNotEmpty) ...[
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
                    ThickCard(
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
                    ThickCard(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.small),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(
                                AppRadius.button,
                              ),
                              child: Stack(
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
                                        child: Image.memory(
                                          photo,
                                          fit: BoxFit.fill,
                                        ),
                                      ),
                                    ),
                                  ),
                                  Positioned(
                                    top: AppSpacing.small,
                                    right: AppSpacing.small,
                                    child: IconButton.filledTonal(
                                      key: const Key('video-asset-rotate'),
                                      tooltip: '旋轉',
                                      onPressed: state.busy
                                          ? null
                                          : notifier.rotate,
                                      icon: const Icon(Icons.rotate_right),
                                    ),
                                  ),
                                ],
                              ),
                            ),
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
                                  ThickButton(
                                    buttonKey: const Key('video-asset-regions'),
                                    style: ThickStyle.dark,
                                    icon: Icons.crop_free,
                                    label:
                                        '標區域（${asset.regions.values.where((b) => b != null).length}'
                                        '／${asset.regions.length}）',
                                    shadow: AppShadows.soft,
                                    onPressed: () => context.go(
                                      '/videos/${widget.projectId}/assets/'
                                      '${widget.assetKey}/regions',
                                    ),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}

/// 略過（程式判斷可不可以）：已略過（可取消）、可以略過、只靠它的段不能略過。
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
      return ThickCard(
        child: ListTile(
          leading: const Icon(Icons.block),
          title: const Text('已略過'),
          subtitle: const Text('產生影片時不用這張'),
          trailing: ThickButton(
            buttonKey: const Key('video-asset-unskip'),
            style: ThickStyle.light,
            label: '取消略過',
            shadow: AppShadows.soft,
            onPressed: busy ? null : onUnskip,
          ),
        ),
      );
    }
    if (!asset.skippable) {
      return ThickCard(
        child: Padding(
          padding: videoCardInset,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                textCardHint(asset.skipBlockedSegments),
                style: text.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.small),
              ThickButton(
                buttonKey: const Key('video-asset-skip'),
                style: ThickStyle.light,
                icon: Icons.text_fields,
                label: '拍不了，改用文字卡',
                shadow: AppShadows.soft,
                onPressed: busy ? null : onSkip,
              ),
            ],
          ),
        ),
      );
    }
    return Align(
      alignment: Alignment.centerLeft,
      child: ThickButton(
        buttonKey: const Key('video-asset-skip'),
        style: ThickStyle.light,
        icon: Icons.block,
        label: '略過這張',
        shadow: AppShadows.soft,
        onPressed: busy ? null : onSkip,
      ),
    );
  }
}
