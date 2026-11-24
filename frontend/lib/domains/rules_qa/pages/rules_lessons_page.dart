import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../../host/state/host_labels.dart';
import '../data/rules_qa_models.dart';
import '../state/rules_lessons_state.dart';

/// 規則教學正式頁面：有教材的遊戲清單，可以搜尋名稱、篩選有影片或可以問規則的遊戲。
///
/// Stitch 版面（docs/ui/stitch/）：木紋背景，文字放在卡片上，遊戲卡片有厚度、按得下去；
/// 手機的浮動導覽列蓋住的高度（MediaQuery 底部 padding）留在清單最下面。
class RulesLessonsPage extends ConsumerWidget {
  const RulesLessonsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lessons = ref.watch(rulesLessonsProvider);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    final text = Theme.of(context).textTheme;

    Widget centered(Widget child) => Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: ThickCard(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: child,
          ),
        ),
      ),
    );

    final body = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: lessons.when(
          skipLoadingOnRefresh: false,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => centered(
            Column(
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
          data: (items) => items.isEmpty
              ? centered(Text('目前還沒有可以教學的遊戲', style: text.bodyLarge))
              : _LessonList(items),
        ),
      ),
    );

    return Scaffold(
      key: const Key('rules-lessons-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? body
            : WoodBackground(child: body),
      ),
    );
  }
}

/// 頁首（標題、搜尋、篩選）、筆數與遊戲卡片。
class _LessonList extends ConsumerWidget {
  const _LessonList(this.items);

  final List<RulesLessonSummary> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = ref.watch(lessonsQueryProvider);
    final shown = filterLessons(items, query);
    const gap = SizedBox(height: AppSpacing.medium);
    return ListView(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.medium,
        AppSpacing.medium,
        AppSpacing.medium + MediaQuery.paddingOf(context).bottom,
      ),
      children: [
        _Header(items: items, query: query),
        gap,
        GlassBar(
          child: Row(
            children: [
              const Icon(
                Icons.menu_book_outlined,
                color: AppColors.primaryText,
              ),
              const SizedBox(width: AppSpacing.small),
              Expanded(
                child: Text(
                  '選好遊戲就能看教學或問規則',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              Text(
                '共 ${shown.length} 款',
                style: Theme.of(context).textTheme.labelLarge,
              ),
            ],
          ),
        ),
        gap,
        if (shown.isEmpty)
          ThickCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Text(
                '找不到符合的遊戲',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ),
        for (final item in shown)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: _LessonCard(item),
          ),
      ],
    );
  }
}

/// 頁首白卡：標題、說明、搜尋框與篩選膠囊。
class _Header extends ConsumerWidget {
  const _Header({required this.items, required this.query});

  final List<RulesLessonSummary> items;
  final LessonsQuery query;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final notifier = ref.read(lessonsQueryProvider.notifier);
    return ThickCard(
      key: const Key('rules-lessons-header'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '規則教學與問答',
              style: text.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text(
              '選一款遊戲，看教學影片或直接問規則',
              style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.medium),
            TextField(
              key: const Key('rules-search'),
              onChanged: notifier.setSearch,
              decoration: const InputDecoration(
                hintText: '搜尋遊戲名稱',
                prefixIcon: Icon(Icons.search),
              ),
            ),
            const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.small,
              children: [
                for (final (filter, label) in const [
                  (LessonFilter.all, '全部'),
                  (LessonFilter.video, '有教學影片'),
                  (LessonFilter.rulebook, '可以問規則'),
                ])
                  _FilterPill(
                    label: '$label（${lessonCount(items, filter)}）',
                    selected: query.filter == filter,
                    onTap: () => notifier.setFilter(filter),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 篩選膠囊：選取時深炭底白字，其他是白底細框。
class _FilterPill extends StatelessWidget {
  const _FilterPill({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: selected ? AppColors.ink : AppColors.surface,
        shape: StadiumBorder(
          side: BorderSide(color: selected ? AppColors.ink : AppColors.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.medium,
              vertical: AppSpacing.small,
            ),
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelLarge!.copyWith(
                color: selected ? AppColors.surface : AppColors.ink,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 名稱首字方塊的配色，依遊戲編號固定（同一款遊戲每次都是同一個顏色）。
const _tileColors = [
  (AppColors.primaryTint, AppColors.primaryText),
  (AppColors.sageTint, AppColors.sage),
  (AppColors.amberTint, AppColors.amberText),
  (AppColors.neutralTint, AppColors.ink),
];

class _LessonCard extends StatelessWidget {
  const _LessonCard(this.item);

  final RulesLessonSummary item;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final (tint, ink) = _tileColors[item.gameId % _tileColors.length];
    return ThickCard(
      key: const Key('rules-lesson-card'),
      onTap: () => context.go('/rules/${item.gameId}'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Row(
          children: [
            // 沒有遊戲圖片：用名稱的第一個字當縮圖
            Container(
              width: AppSizes.entryIconBox + AppSpacing.medium,
              height: AppSizes.entryIconBox + AppSpacing.medium,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: tint,
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
              child: Text(
                item.gameName.isEmpty ? '？' : item.gameName.characters.first,
                style: text.headlineMedium!.copyWith(
                  color: ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.medium),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.gameName,
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
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
                        )
                      else
                        const PillBadge(
                          label: '還沒有影片',
                          icon: Icons.videocam_off_outlined,
                        ),
                      if (item.hasRulebook)
                        const PillBadge(
                          label: '可以問規則',
                          tone: PillTone.players,
                          icon: Icons.chat_bubble_outline,
                        ),
                      // 目前只有這款遊戲有 AI 語音主持（入口在規則教學頁頁首）
                      if (item.gameName == hostGameName)
                        const PillBadge(
                          label: '有語音主持',
                          tone: PillTone.duration,
                          icon: Icons.record_voice_over_outlined,
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.inkMuted),
          ],
        ),
      ),
    );
  }
}
