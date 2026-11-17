import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/rules_qa_models.dart';
import '../state/rules_lessons_state.dart';

/// 規則教學正式頁面：有教材的遊戲清單。
class RulesLessonsPage extends ConsumerWidget {
  const RulesLessonsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lessons = ref.watch(rulesLessonsProvider);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      key: const Key('rules-lessons-page'),
      appBar: AppBar(title: const Text('規則教學')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: lessons.when(
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
                      onPressed: ref.read(rulesLessonsProvider.notifier).reload,
                      child: const Text('重試'),
                    ),
                  ],
                ),
              ),
            ),
            data: (items) => items.isEmpty
                ? Center(child: Text('目前還沒有可以教學的遊戲', style: text.bodyLarge))
                : ListView(
                    padding: const EdgeInsets.all(AppSpacing.medium),
                    children: [
                      Text(
                        '選一款遊戲，看教學影片或直接問規則',
                        style: text.bodyMedium!.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.medium),
                      for (final item in items)
                        Padding(
                          padding: const EdgeInsets.only(
                            bottom: AppSpacing.medium,
                          ),
                          child: _LessonCard(item),
                        ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

class _LessonCard extends StatelessWidget {
  const _LessonCard(this.item);

  final RulesLessonSummary item;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go('/rules/${item.gameId}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.gameName,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppSpacing.small),
                    Wrap(
                      spacing: AppSpacing.small,
                      runSpacing: AppSpacing.xSmall,
                      children: [
                        if (item.hasVideo)
                          const PillBadge(
                            label: '有教學影片',
                            tone: PillTone.accent,
                            icon: Icons.play_circle_outline,
                          ),
                        if (item.hasRulebook)
                          const PillBadge(
                            label: '可以問規則',
                            tone: PillTone.players,
                            icon: Icons.menu_book_outlined,
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
