import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_rulebook_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 拍規則書（`/videos/:id/rulebook`，2026-11-22 永傑決定）：依頁面的順序拍每一頁，
/// 每張標出清晰度（太模糊要重拍）、可以刪掉重拍；拍好後「讀取規則書並產生草稿」。
class VideoRulebookPage extends ConsumerStatefulWidget {
  const VideoRulebookPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoRulebookPage> createState() => _VideoRulebookPageState();
}

class _VideoRulebookPageState extends ConsumerState<VideoRulebookPage> {
  String get _id => widget.projectId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) ref.read(videoRulebookProvider(_id).notifier).load();
    });
  }

  Future<void> _start() async {
    final ok = await ref.read(videoRulebookProvider(_id).notifier).start();
    if (ok && mounted) context.go('/videos/$_id');
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoRulebookProvider(_id));
    final notifier = ref.read(videoRulebookProvider(_id).notifier);
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    return VideoScaffold(
      key: const Key('video-rulebook-page'),
      title: '拍規則書',
      bottom: VideoBottomActions(
        children: [
          ThickButton(
            buttonKey: const Key('video-rulebook-add'),
            style: ThickStyle.light,
            expand: true,
            icon: Icons.photo_camera_outlined,
            label: state.progress ?? '拍照或選圖',
            shadow: AppShadows.soft,
            onPressed: state.busy ? null : notifier.addPhotos,
          ),
          ThickButton(
            buttonKey: const Key('video-rulebook-start'),
            style: ThickStyle.primary,
            expand: true,
            label: '讀取規則書並產生草稿',
            shadow: AppShadows.soft,
            onPressed: state.canStart ? _start : null,
          ),
        ],
      ),
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            ThickCard(
              child: Padding(
                padding: videoCardInset,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.photo_camera_outlined,
                      color: AppColors.primaryText,
                    ),
                    const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                    Expanded(
                      child: Text(
                        '依頁面的順序拍規則書的每一頁（一張一頁，整頁入鏡、不要反光）。'
                        '可以一次選很多張；拍壞的照片可以刪掉再補拍，新拍的會排在最後。',
                        style: text.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.medium),
            if (state.rulebook?.read ?? false) ...[
              const NoticeBanner(text: '這些照片已經讀過了，重新產生草稿時不會再讀；加減照片後才會重新讀'),
              const SizedBox(height: AppSpacing.medium),
            ],
            if (state.error != null) ...[
              NoticeBanner(text: state.error!, isError: true),
              const SizedBox(height: AppSpacing.medium),
            ],
            if (state.hasBlurry) ...[
              const NoticeBanner(
                text: '有照片太模糊，AI 會讀錯字：請刪掉後重拍，才能繼續',
                isError: true,
              ),
              const SizedBox(height: AppSpacing.medium),
            ],
            if (state.loading && state.rulebook == null)
              const Center(child: CircularProgressIndicator())
            else if (state.photos.isEmpty)
              ThickCard(
                child: Padding(
                  padding: videoCardInset,
                  child: Text(
                    '還沒有照片',
                    textAlign: TextAlign.center,
                    style: text.bodyMedium!.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              )
            else ...[
              SectionBar(
                title: '已拍的頁面',
                icon: Icons.photo_library_outlined,
                trailing: Text(
                  '已拍 ${state.photos.length} 頁',
                  style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
                ),
              ),
              for (final photo in state.photos) ...[
                const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
                _PhotoTile(
                  projectId: _id,
                  photo: photo,
                  busy: state.busy,
                  onDelete: () => notifier.delete(photo.index),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _PhotoTile extends ConsumerWidget {
  const _PhotoTile({
    required this.projectId,
    required this.photo,
    required this.busy,
    required this.onDelete,
  });

  final String projectId;
  final RulebookPhoto photo;
  final bool busy;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final image = ref.watch(
      rulebookPhotoProvider((
        projectId: projectId,
        index: photo.index,
        id: photo.id,
      )),
    );
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: Key('video-rulebook-photo-${photo.index}'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
        child: Row(
          children: [
            SizedBox(
              width: 72,
              height: 96,
              child: image.when(
                loading: () => const Center(
                  child: SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
                error: (_, _) => const Icon(Icons.broken_image_outlined),
                data: (bytes) => Image.memory(bytes, fit: BoxFit.cover),
              ),
            ),
            const SizedBox(width: AppSpacing.medium),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '第 ${photo.index} 張',
                    style: text.titleSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (photo.qualityMessage != null) ...[
                    const SizedBox(height: AppSpacing.xSmall),
                    PillBadge(
                      label: photo.qualityMessage!,
                      tone: photo.quality == 'bad'
                          ? PillTone.duration
                          : PillTone.neutral,
                      icon: photo.quality == 'bad'
                          ? Icons.error_outline
                          : Icons.info_outline,
                    ),
                  ],
                ],
              ),
            ),
            IconButton(
              key: Key('video-rulebook-delete-${photo.index}'),
              tooltip: '刪掉這張',
              onPressed: busy ? null : onDelete,
              icon: const Icon(Icons.delete_outline),
            ),
          ],
        ),
      ),
    );
  }
}
