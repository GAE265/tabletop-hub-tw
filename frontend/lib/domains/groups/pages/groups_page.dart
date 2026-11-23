import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import '../state/groups_calendar_state.dart';
import 'group_detail_page.dart';
import 'group_form_page.dart';
import 'widgets/group_widgets.dart';
import 'widgets/month_calendar.dart';

/// 揪團月曆正式頁面。手機版頁首、月曆在上，當日列表在下；平板與桌機左右並排。
///
/// 版面依 Stitch 設計（docs/ui/stitch/）：木紋背景，文字一律放在卡片或白底條上。
/// 手機的畫面框架已經畫了木紋、導覽列浮在頁面上，這裡不再畫木紋，並在捲動內容最下面留出導覽列的高度。
class GroupsPage extends ConsumerWidget {
  const GroupsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const header = _Header(key: Key('groups-header'));
    const calendar = MonthCalendar(key: Key('groups-calendar'));
    const dayList = _DayList(key: Key('groups-day-list'));
    const gap = AppSpacing.medium;
    // 開團入口在當天列表裡（有揪團時在最下方，沒有時在空狀態），只有一個
    final padding = EdgeInsets.fromLTRB(
      gap,
      gap,
      gap,
      gap + MediaQuery.paddingOf(context).bottom,
    );

    final body = switch (context.screenSize) {
      ScreenSize.mobile => SingleChildScrollView(
        padding: padding,
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            header,
            SizedBox(height: gap),
            calendar,
            SizedBox(height: AppSpacing.large),
            dayList,
          ],
        ),
      ),
      _ => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.splitContentMaxWidth,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 3,
                child: SingleChildScrollView(
                  padding: padding,
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      header,
                      SizedBox(height: gap),
                      calendar,
                    ],
                  ),
                ),
              ),
              Expanded(
                flex: 2,
                child: SingleChildScrollView(padding: padding, child: dayList),
              ),
            ],
          ),
        ),
      ),
    };

    final content = SafeArea(bottom: false, child: body);
    return Scaffold(
      key: const Key('groups-page'),
      backgroundColor: Colors.transparent,
      body: WoodBackground.isPaintedAbove(context)
          ? content
          : WoodBackground(child: content),
    );
  }
}

/// 頁首白底卡：標題、說明與開團主篩選。
class _Header extends StatelessWidget {
  const _Header({super.key});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      radius: AppRadius.card,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.calendar_month_outlined,
                  color: AppColors.primaryText,
                ),
                const SizedBox(width: AppSpacing.small),
                Expanded(
                  child: Text(
                    '找人一起玩・揪團月曆',
                    style: text.headlineSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text(
              '選取日期看當日開團，隨時加入或自己當團主',
              style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.medium),
            const OrganizerFilter(),
          ],
        ),
      ),
    );
  }
}

/// 開啟開團表單；[date] 為預設日期。
Future<void> openGroupForm(
  BuildContext context,
  WidgetRef ref, {
  required DateTime date,
}) {
  ref.read(groupFormProvider.notifier).reset();
  return Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => GroupFormPage(initial: GroupFormData(date: date)),
    ),
  );
}

/// 選取日期的揪團列表。月曆載入中或失敗時不顯示（月曆那邊已經有提示）。
class _DayList extends ConsumerWidget {
  const _DayList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    if (state.groups.isLoading || state.groups.hasError) {
      return const SizedBox.shrink();
    }
    final date = state.selectedDate;
    final groups = ref.watch(selectedDayGroupsProvider);
    final text = Theme.of(context).textTheme;
    void create() => openGroupForm(context, ref, date: date);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionBar(
          key: const Key('groups-day-header'),
          title: '${date.month}/${date.day}（${weekdayLabel(date)}）的揪團',
          trailing: groups.isEmpty
              ? null
              : PillBadge(
                  label: '共 ${groups.length} 場',
                  tone: PillTone.players,
                ),
        ),
        const SizedBox(height: AppSpacing.medium),
        if (groups.isEmpty)
          ThickCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Column(
                children: [
                  Text('這天還沒有人揪團', style: text.titleMedium),
                  const SizedBox(height: AppSpacing.medium),
                  ThickButton(
                    buttonKey: const Key('groups-empty-create'),
                    // 和列表下方的「我要揪團」同一個樣子
                    style: ThickStyle.dark,
                    expand: true,
                    onPressed: create,
                    icon: Icons.group_add_outlined,
                    label: '我要揪團',
                  ),
                ],
              ),
            ),
          ),
        for (final group in groups)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: GroupCard(
              group: group,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => GroupDetailPage(groupId: group.id),
                ),
              ),
            ),
          ),
        if (groups.isNotEmpty)
          ThickButton(
            buttonKey: const Key('groups-day-create'),
            style: ThickStyle.dark,
            expand: true,
            onPressed: create,
            icon: Icons.group_add_outlined,
            label: '我要揪團',
          ),
      ],
    );
  }
}
