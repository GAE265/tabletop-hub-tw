import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../state/video_draft_state.dart';
import '../state/video_job_state.dart';
import '../state/video_projects_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 專案的步驟（整個遊戲一支影片，design.md D17：頁面文字那一步從店員流程移除）。
/// 拍規則書的專案前面多一步「規則書」（2026-11-22 永傑決定）。
List<String> _stepsOf(VideoProject project) => [
  if (project.rulebook == 'photos') '規則書',
  '草稿',
  '素材',
  '影片',
];

int _stepIndex(VideoProject project) {
  final offset = project.rulebook == 'photos' ? 1 : 0;
  return switch (project.step) {
    'rulebook' => 0,
    'assets' => 1 + offset,
    'render' => 2 + offset,
    'done' => 3 + offset,
    _ => offset, // draft；舊的單章專案的 pages 也從草稿算起
  };
}

/// 專案總覽（`/videos/:id`）：目前在哪一步、下一步做什麼、最近一個工作的進度。
class VideoProjectPage extends ConsumerStatefulWidget {
  const VideoProjectPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoProjectPage> createState() => _VideoProjectPageState();
}

class _VideoProjectPageState extends ConsumerState<VideoProjectPage> {
  String get _id => widget.projectId;

  @override
  void initState() {
    super.initState();
    // 離開再回來：最近的工作還在進行就接著查
    Future.microtask(() {
      if (mounted) ref.read(videoJobProvider(_id).notifier).resume();
    });
  }

  @override
  Widget build(BuildContext context) {
    final project = ref.watch(videoProjectProvider(_id));
    return Scaffold(
      key: const Key('video-project-page'),
      appBar: AppBar(title: const Text('影片專案')),
      body: VideoPageBody(
        child: project.when(
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
                    onPressed: () => ref.invalidate(videoProjectProvider(_id)),
                    child: const Text('重試'),
                  ),
                ],
              ),
            ),
          ),
          data: (project) => _Overview(project: project),
        ),
      ),
    );
  }
}

class _Overview extends ConsumerWidget {
  const _Overview({required this.project});

  final VideoProject project;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final id = project.id;
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final steps = _stepsOf(project);
    final current = _stepIndex(project);
    final photos = project.rulebook == 'photos';
    // 拍規則書的專案多一步，後面的步驟往後一格
    final draftAt = photos ? 1 : 0;
    // 草稿不擋流程：有草稿就可以直接去拍素材
    final hasDraft = ref.watch(videoDraftProvider(id)).value != null;
    final next = switch (project.step) {
      'rulebook' => ('下一步：拍規則書', '/videos/$id/rulebook'),
      'assets' => ('下一步：拍素材', '/videos/$id/assets'),
      'render' => ('下一步：產生影片', '/videos/$id/render'),
      'done' => ('看影片', '/videos/$id/watch'),
      _ when hasDraft => ('下一步：拍素材', '/videos/$id/assets'),
      _ => ('查看草稿進度', '/videos/$id/draft'),
    };
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        Text(project.title, style: text.titleLarge),
        const SizedBox(height: AppSpacing.large),
        VideoJobCard(projectId: id),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.small),
            child: Column(
              children: [
                for (final (i, label) in steps.indexed)
                  ListTile(
                    key: Key('video-step-$i'),
                    leading: Icon(
                      i < current
                          ? Icons.check_circle
                          : i == current
                          ? Icons.radio_button_checked
                          : Icons.radio_button_unchecked,
                      color: i <= current
                          ? scheme.primary
                          : scheme.onSurfaceVariant,
                    ),
                    title: Text(label),
                    subtitle: i == current ? const Text('目前在這一步') : null,
                    // 已經做過的步驟可以回去改
                    onTap: switch (i - draftAt) {
                      -1 => () => context.go('/videos/$id/rulebook'),
                      0 when current >= draftAt => () => context.go(
                        '/videos/$id/draft',
                      ),
                      1 when current >= 1 + draftAt || hasDraft =>
                        () => context.go('/videos/$id/assets'),
                      2 when current >= 2 + draftAt => () => context.go(
                        '/videos/$id/render',
                      ),
                      _ => null,
                    },
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.large),
        FilledButton(
          key: const Key('video-next-step'),
          onPressed: () => context.go(next.$2),
          child: Text(next.$1),
        ),
      ],
    );
  }
}
