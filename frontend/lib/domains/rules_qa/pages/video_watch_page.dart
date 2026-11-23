import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/platform/video_file_player.dart';
import '../data/video_studio_models.dart';
import '../state/video_render_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 看影片（`/videos/:id/watch`，外觀決定）：播放器寬度填滿、16:9、可以切全螢幕；
/// 段清單在播放器下方，點一段跳到那個時間點。
class VideoWatchPage extends ConsumerStatefulWidget {
  const VideoWatchPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoWatchPage> createState() => _VideoWatchPageState();
}

class _VideoWatchPageState extends ConsumerState<VideoWatchPage> {
  final _seek = VideoSeekController();

  String get _id => widget.projectId;

  @override
  void dispose() {
    _seek.dispose();
    super.dispose();
  }

  Widget _message(
    String text, {
    required String action,
    required VoidCallback onPressed,
  }) => Center(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.large),
      child: ThickCard(
        child: Padding(
          padding: videoCardInset,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(text, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.medium),
              ThickButton(
                style: ThickStyle.primary,
                label: action,
                shadow: AppShadows.soft,
                onPressed: onPressed,
              ),
            ],
          ),
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final render = ref.watch(videoRenderProvider(_id));
    return VideoScaffold(
      key: const Key('video-watch-page'),
      title: '看影片',
      body: VideoPageBody(
        child: render.when(
          skipLoadingOnRefresh: false,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _message(
            error is ApiException ? error.message : '發生未知錯誤',
            action: '重試',
            onPressed: () => ref.invalidate(videoRenderProvider(_id)),
          ),
          data: (value) => value == null
              ? _message(
                  '還沒有產生影片',
                  action: '去產生影片',
                  onPressed: () => context.go('/videos/$_id/render'),
                )
              : _Watch(projectId: _id, render: value, seek: _seek),
        ),
      ),
    );
  }
}

class _Watch extends ConsumerWidget {
  const _Watch({
    required this.projectId,
    required this.render,
    required this.seek,
  });

  final String projectId;
  final VideoRender render;
  final VideoSeekController seek;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bytes = ref.watch(videoRenderVideoProvider(projectId));
    final player = ref.watch(videoFilePlayerProvider);
    final text = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        AspectRatio(
          key: const Key('video-watch-player'),
          aspectRatio: 16 / 9,
          child: bytes.when(
            skipLoadingOnRefresh: false,
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => Center(
              child: ThickCard(
                child: Padding(
                  padding: videoCardInset,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(error is ApiException ? error.message : '影片下載失敗'),
                      const SizedBox(height: AppSpacing.small),
                      ThickButton(
                        style: ThickStyle.primary,
                        label: '重試',
                        shadow: AppShadows.soft,
                        onPressed: () =>
                            ref.invalidate(videoRenderVideoProvider(projectId)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            data: (data) => player.build(context, bytes: data, seek: seek),
          ),
        ),
        const SizedBox(height: AppSpacing.medium),
        ThickCard(
          key: const Key('video-watch-info'),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.small),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.medium,
                    vertical: AppSpacing.small,
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          render.segments.isEmpty ? '影片資訊' : '段清單',
                          style: text.titleMedium!.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      Text(
                        '總長 ${render.totalSeconds.toStringAsFixed(1)} 秒',
                        style: text.bodyMedium,
                      ),
                    ],
                  ),
                ),
                for (final (i, segment) in render.segments.indexed)
                  ListTile(
                    key: Key('video-watch-segment-${segment.segmentKey}'),
                    leading: Text('第 ${i + 1} 段', style: text.labelLarge),
                    title: Text(segment.title),
                    trailing: Text(
                      formatPlaybackTime(
                        Duration(
                          milliseconds: (segment.startSeconds * 1000).round(),
                        ),
                      ),
                    ),
                    onTap: () => seek.seekTo(
                      Duration(
                        milliseconds: (segment.startSeconds * 1000).round(),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
