import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../data/video_image_size.dart';
import '../state/video_assets_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/region_editor.dart';
import 'widgets/video_studio_widgets.dart';

/// 標區域（`/videos/:id/assets/:key/regions`，外觀決定）：每次都顯示「用四個角對齊框線」；
/// 區域清單顯示已標幾個與名稱；沒儲存就離開時先提示。
/// 目前區域顯示白話說明與「第 N 段會用到」；照片拍不到時可以略過（2026-11-22 永傑決定）。
class VideoRegionsPage extends ConsumerStatefulWidget {
  const VideoRegionsPage({
    required this.projectId,
    required this.assetKey,
    super.key,
  });

  final String projectId;
  final String assetKey;

  @override
  ConsumerState<VideoRegionsPage> createState() => _VideoRegionsPageState();
}

class _VideoRegionsPageState extends ConsumerState<VideoRegionsPage> {
  VideoAssetRef get _ref =>
      (projectId: widget.projectId, assetKey: widget.assetKey);

  String get _assetPath =>
      '/videos/${widget.projectId}/assets/${widget.assetKey}';

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (!mounted) return;
      ref.read(videoRegionsProvider(_ref).notifier).load();
      // 直接打開這一頁（例如重新整理）時，照片還沒讀
      if (ref.read(videoAssetProvider(_ref)).photo == null) {
        ref.read(videoAssetProvider(_ref).notifier).load();
      }
    });
  }

  Future<void> _save() async {
    final ok = await ref.read(videoRegionsProvider(_ref).notifier).save();
    if (ok && mounted) context.go(_assetPath);
  }

  Future<void> _confirmLeave() async {
    final leave = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        content: const Text('還有沒儲存的區域，要離開嗎？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('繼續標'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('離開'),
          ),
        ],
      ),
    );
    if ((leave ?? false) && mounted) context.go(_assetPath);
  }

  /// 略過前說明影響，並建議照片拍得到的話重拍。
  Future<void> _confirmSkip(String name, List<int> segments) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('略過「$name」？'),
        content: Text(
          segments.isEmpty
              ? '目前沒有段用到這個區域。照片拍得到的話，建議重拍。'
              : '略過後，第 ${segments.join('、')} 段的框選、標籤或移動會拿掉。'
                    '照片拍得到的話，建議重拍。',
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
      await ref
          .read(videoRegionsProvider(_ref).notifier)
          .setRegionSkipped(name, true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoRegionsProvider(_ref));
    final notifier = ref.read(videoRegionsProvider(_ref).notifier);
    final assetState = ref.watch(videoAssetProvider(_ref));
    final photo = assetState.photo;
    final orientation = assetState.asset?.orientation ?? 0;
    final size = photo == null ? null : imageSizeOf(photo);
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    return PopScope(
      canPop: !state.dirty,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _confirmLeave();
      },
      child: VideoScaffold(
        key: const Key('video-regions-page'),
        title: '標區域',
        bottom: VideoBottomActions(
          children: [
            ThickButton(
              buttonKey: const Key('video-regions-save'),
              style: ThickStyle.primary,
              expand: true,
              icon: Icons.save_outlined,
              label: state.saving ? '儲存中…' : '儲存',
              shadow: AppShadows.soft,
              onPressed: state.canSave ? _save : null,
            ),
          ],
        ),
        // 不捲動：拖框的手勢才不會被捲動搶走；照片縮到剩下的高度
        body: VideoPageBody(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.medium),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ThickCard(
                  key: const Key('video-regions-panel'),
                  child: Padding(
                    padding: const EdgeInsets.all(
                      AppSpacing.small + AppSpacing.xSmall,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          '用四個角對齊框線',
                          style: text.bodySmall!.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.small),
                        Text(
                          '已標 ${state.doneCount}／${state.names.length}',
                          style: text.titleSmall!.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.small),
                        Wrap(
                          spacing: AppSpacing.small,
                          runSpacing: AppSpacing.xSmall,
                          children: [
                            for (final name in state.names)
                              ChoiceChip(
                                key: Key('video-region-chip-$name'),
                                avatar: state.skipped.contains(name)
                                    ? const Icon(Icons.block)
                                    : state.boxes[name] != null
                                    ? const Icon(Icons.check)
                                    : null,
                                label: Text(name),
                                selected: state.current == name,
                                onSelected: (_) => notifier.select(name),
                              ),
                          ],
                        ),
                        if (state.current case final name?) ...[
                          const SizedBox(height: AppSpacing.small),
                          if (state.hints[name] case final hint?
                              when hint.isNotEmpty)
                            Text(
                              hint,
                              key: const Key('video-region-hint'),
                              style: text.bodyMedium,
                            ),
                          Text(
                            regionSegmentsText(
                              state.segments[name] ?? const [],
                            ),
                            key: const Key('video-region-segments'),
                            style: text.bodySmall!.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: AppSpacing.xSmall),
                          if (state.skipped.contains(name))
                            Row(
                              children: [
                                const Icon(Icons.block),
                                const SizedBox(width: AppSpacing.small),
                                const Expanded(child: Text('已略過：照片拍不到這個區域')),
                                TextButton(
                                  key: const Key('video-region-unskip'),
                                  onPressed: state.saving
                                      ? null
                                      : () => notifier.setRegionSkipped(
                                          name,
                                          false,
                                        ),
                                  child: const Text('取消略過'),
                                ),
                              ],
                            )
                          else
                            Align(
                              alignment: Alignment.centerLeft,
                              child: TextButton.icon(
                                key: const Key('video-region-skip'),
                                onPressed: state.saving
                                    ? null
                                    : () => _confirmSkip(
                                        name,
                                        state.segments[name] ?? const [],
                                      ),
                                icon: const Icon(Icons.block),
                                label: const Text('照片拍不到這個區域'),
                              ),
                            ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.medium),
                if (state.error != null) ...[
                  NoticeBanner(text: state.error!, isError: true),
                  const SizedBox(height: AppSpacing.medium),
                ],
                if (state.tooSmall.isNotEmpty) ...[
                  const NoticeBanner(text: '框太小，請拉大一點', isError: true),
                  const SizedBox(height: AppSpacing.medium),
                ],
                if (photo == null || size == null)
                  const Center(child: CircularProgressIndicator())
                else
                  Flexible(
                    child: Align(
                      alignment: Alignment.topCenter,
                      child: RegionEditor(
                        photo: photo,
                        aspectRatio: displaySize(size, orientation).aspectRatio,
                        orientation: orientation,
                        boxes: state.boxes,
                        current: state.current,
                        onChanged: notifier.setBox,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
