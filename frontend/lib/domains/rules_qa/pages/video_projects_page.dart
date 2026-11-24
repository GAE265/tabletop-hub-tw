import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
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
    return VideoScaffold(
      key: const Key('video-projects-page'),
      title: '規則影片',
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            // 頁首卡：說明與「新增專案」
            ThickCard(
              key: const Key('video-projects-header'),
              child: Padding(
                padding: videoCardInset,
                child: Row(
                  children: [
                    Container(
                      width: AppSizes.entryIconBox,
                      height: AppSizes.entryIconBox,
                      decoration: BoxDecoration(
                        color: AppColors.primaryTint,
                        borderRadius: BorderRadius.circular(AppRadius.button),
                      ),
                      child: const Icon(
                        Icons.movie_outlined,
                        color: AppColors.primaryText,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.medium),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '規則影片生產器',
                            style: text.titleLarge!.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          Text(
                            '選一款遊戲，把規則書做成教學影片',
                            style: text.bodySmall!.copyWith(
                              color: AppColors.inkMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: AppSpacing.small),
                    ThickButton(
                      buttonKey: const Key('video-project-new'),
                      style: ThickStyle.primary,
                      icon: Icons.add,
                      label: '新增專案',
                      shadow: AppShadows.soft,
                      onPressed: () => context.go('/videos/new'),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.large),
            ...projects.when(
              skipLoadingOnRefresh: false,
              loading: () => const [Center(child: CircularProgressIndicator())],
              error: (error, _) => [
                ThickCard(
                  child: Padding(
                    padding: videoCardInset,
                    child: Column(
                      children: [
                        Text(
                          error is ApiException ? error.message : '發生未知錯誤',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: AppSpacing.medium),
                        ThickButton(
                          style: ThickStyle.primary,
                          label: '重試',
                          shadow: AppShadows.soft,
                          onPressed: ref
                              .read(videoProjectsProvider.notifier)
                              .reload,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              data: (items) => items.isEmpty
                  ? [
                      ThickCard(
                        child: Padding(
                          padding: videoCardInset,
                          child: Column(
                            children: [
                              Text('還沒有專案', style: text.titleMedium),
                              const SizedBox(height: AppSpacing.small),
                              Text(
                                '按右上角的「新增專案」開始',
                                textAlign: TextAlign.center,
                                style: text.bodyMedium,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ]
                  : [
                      SectionBar(
                        title: '我的專案',
                        icon: Icons.video_library_outlined,
                        trailing: Text(
                          '${items.length} 個',
                          style: text.bodyMedium!.copyWith(
                            color: AppColors.inkMuted,
                          ),
                        ),
                      ),
                      for (final project in items) ...[
                        const SizedBox(height: AppSpacing.medium),
                        _ProjectCard(project),
                      ],
                    ],
            ),
          ],
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
    return ThickCard(
      key: Key('video-project-${project.id}'),
      onTap: () => context.go('/videos/${project.id}'),
      child: Padding(
        padding: videoCardInset,
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    project.title,
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
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
    );
  }
}
