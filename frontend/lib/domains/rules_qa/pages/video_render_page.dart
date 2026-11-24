import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../state/video_assets_state.dart';
import '../state/video_draft_state.dart';
import '../state/video_job_state.dart';
import '../state/video_render_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 產生影片（`/videos/:id/render`，design.md D16 與外觀決定）：還缺什麼（缺東西時按鈕停用並連到
/// 素材頁）、「產生影片」、進度（真正的百分比與目前在做什麼）、失敗原因與重試、最近的成品。
class VideoRenderPage extends ConsumerStatefulWidget {
  const VideoRenderPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoRenderPage> createState() => _VideoRenderPageState();
}

class _VideoRenderPageState extends ConsumerState<VideoRenderPage> {
  String get _id => widget.projectId;

  @override
  void initState() {
    super.initState();
    // 離開再回來：產生中就接著查
    Future.microtask(() {
      if (mounted) ref.read(videoJobProvider(_id).notifier).resume();
    });
  }

  @override
  Widget build(BuildContext context) {
    final readiness = ref.watch(videoReadinessProvider(_id));
    final render = ref.watch(videoRenderProvider(_id));
    final draft = ref.watch(videoDraftProvider(_id));
    final running = ref.watch(videoJobProvider(_id)).running;
    final ready = readiness.value?.ready ?? false;
    return VideoScaffold(
      key: const Key('video-render-page'),
      title: '產生影片',
      bottom: VideoBottomActions(
        children: [
          ThickButton(
            buttonKey: const Key('video-render-start'),
            style: ThickStyle.primary,
            expand: true,
            icon: Icons.movie_creation_outlined,
            label: render.value == null ? '產生影片' : '重新產生影片',
            shadow: AppShadows.soft,
            onPressed: ready && !running
                ? ref.read(videoJobProvider(_id).notifier).startRender
                : null,
          ),
        ],
      ),
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            VideoJobCard(projectId: _id),
            readiness.when(
              loading: () => const LinearProgressIndicator(),
              error: (error, _) => ThickCard(
                child: Padding(
                  padding: videoCardInset,
                  child: Text(
                    error is ApiException ? error.message : '讀不到還缺什麼',
                  ),
                ),
              ),
              data: (r) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  VideoReadinessCard(
                    readiness: r,
                    names: {
                      for (final a
                          in draft.value?.assets ?? const <DraftAsset>[])
                        a.assetKey: assetDisplayName(a),
                    },
                  ),
                  if (!r.ready) ...[
                    const SizedBox(
                      height: AppSpacing.small + AppSpacing.xSmall,
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: ThickButton(
                        buttonKey: const Key('video-render-go-assets'),
                        style: ThickStyle.light,
                        icon: Icons.photo_camera_outlined,
                        label: '去拍素材',
                        shadow: AppShadows.soft,
                        onPressed: () => context.go('/videos/$_id/assets'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.medium),
            if (render.value case final value?) _RenderCard(_id, value),
          ],
        ),
      ),
    );
  }
}

/// 最近一次成功的成品。
class _RenderCard extends StatelessWidget {
  const _RenderCard(this.projectId, this.render);

  final String projectId;
  final VideoRender render;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final seconds = render.totalSeconds.toStringAsFixed(1);
    return ThickCard(
      key: const Key('video-render-latest'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '最近的成品',
              style: text.titleMedium!.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text('總長 $seconds 秒', style: text.bodyLarge),
            Text(
              '重新產生 ${render.reencoded.length} 段、沿用 ${render.reused.length} 段',
              style: text.bodySmall,
            ),
            if (render.estimated)
              Text('沒有設定文字轉語音：旁白是靜音、時間為估計值', style: text.bodySmall),
            const SizedBox(height: AppSpacing.small),
            ThickButton(
              style: ThickStyle.dark,
              icon: Icons.play_circle_outline,
              label: '看影片',
              shadow: AppShadows.soft,
              onPressed: () => context.go('/videos/$projectId/watch'),
            ),
          ],
        ),
      ),
    );
  }
}
