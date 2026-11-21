import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/video_studio_models.dart';
import '../state/video_projects_state.dart';
import 'widgets/video_studio_widgets.dart';

/// 影片專案列表（`/videos`）。
class VideoProjectsPage extends ConsumerWidget {
  const VideoProjectsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final projects = ref.watch(videoProjectsProvider);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      key: const Key('video-projects-page'),
      appBar: AppBar(title: const Text('規則影片')),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('video-project-new'),
        onPressed: () => context.go('/videos/new'),
        icon: const Icon(Icons.add),
        label: const Text('新增專案'),
      ),
      body: VideoPageBody(
        child: projects.when(
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
                    onPressed: ref.read(videoProjectsProvider.notifier).reload,
                    child: const Text('重試'),
                  ),
                ],
              ),
            ),
          ),
          data: (items) => items.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.large),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text('還沒有專案', style: text.titleMedium),
                        const SizedBox(height: AppSpacing.small),
                        Text(
                          '選一款遊戲的一章，把規則書做成教學影片',
                          textAlign: TextAlign.center,
                          style: text.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                )
              : ListView(
                  // 留出浮動按鈕的空間
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.medium,
                    AppSpacing.medium,
                    AppSpacing.medium,
                    AppSpacing.xLarge * 3,
                  ),
                  children: [
                    for (final project in items)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: AppSpacing.medium,
                        ),
                        child: _ProjectCard(project),
                      ),
                  ],
                ),
        ),
      ),
    );
  }
}

String formatVideoTime(DateTime time) {
  final local = time.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.month}/${local.day} ${two(local.hour)}:${two(local.minute)}';
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard(this.project);

  final VideoProject project;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      key: Key('video-project-${project.id}'),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go('/videos/${project.id}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(project.gameName, style: text.titleMedium),
                    const SizedBox(height: AppSpacing.xSmall),
                    Text(
                      '第 ${project.chapterNumber} 章　${project.chapterTitle}',
                      style: text.bodyMedium,
                    ),
                    const SizedBox(height: AppSpacing.small),
                    Wrap(
                      spacing: AppSpacing.small,
                      runSpacing: AppSpacing.xSmall,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        PillBadge(
                          label: videoStepLabel(project.step),
                          tone: PillTone.duration,
                        ),
                        Text(
                          '最後修改 ${formatVideoTime(project.updatedAt)}',
                          style: text.bodySmall,
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
