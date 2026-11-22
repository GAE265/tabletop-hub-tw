import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
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
    return Scaffold(
      key: const Key('video-rulebook-page'),
      appBar: AppBar(title: const Text('拍規則書')),
      bottomNavigationBar: VideoBottomActions(
        children: [
          OutlinedButton.icon(
            key: const Key('video-rulebook-add'),
            onPressed: state.busy ? null : notifier.addPhotos,
            icon: const Icon(Icons.photo_camera_outlined),
            label: Text(state.progress ?? '拍照或選圖'),
          ),
          FilledButton(
            key: const Key('video-rulebook-start'),
            onPressed: state.canStart ? _start : null,
            child: const Text('讀取規則書並產生草稿'),
          ),
        ],
      ),
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            Text(
              '依頁面的順序拍規則書的每一頁（一張一頁，整頁入鏡、不要反光）。'
              '可以一次選很多張；拍壞的照片可以刪掉再補拍，新拍的會排在最後。',
              style: text.bodyMedium,
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
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.large),
                child: Text(
                  '還沒有照片',
                  textAlign: TextAlign.center,
                  style: text.bodyMedium!.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
              )
            else ...[
              Text('已拍 ${state.photos.length} 頁', style: text.titleSmall),
              const SizedBox(height: AppSpacing.small),
              for (final photo in state.photos)
                _PhotoTile(
                  projectId: _id,
                  photo: photo,
                  busy: state.busy,
                  onDelete: () => notifier.delete(photo.index),
                ),
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
    return Card(
      key: Key('video-rulebook-photo-${photo.index}'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.small),
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
                  Text('第 ${photo.index} 張', style: text.titleSmall),
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
