import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/layout/breakpoints.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import '../state/groups_calendar_state.dart';
import 'group_detail_page.dart';
import 'group_form_page.dart';
import 'widgets/group_widgets.dart';
import 'widgets/month_calendar.dart';

/// 揪團月曆正式頁面。手機版月曆在上、當日列表在下；平板與桌機左右並排。
class GroupsPage extends ConsumerWidget {
  const GroupsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const calendar = MonthCalendar(key: Key('groups-calendar'));
    const dayList = _DayList(key: Key('groups-day-list'));
    const padding = EdgeInsets.all(AppSpacing.medium);

    return Scaffold(
      key: const Key('groups-page'),
      // 開團入口在當天列表裡（有揪團時在最下方，沒有時在空狀態），只有一個
      appBar: AppBar(title: const Text('揪團')),
      body: switch (context.screenSize) {
        ScreenSize.mobile => const SingleChildScrollView(
          padding: padding,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
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
            child: const Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 3,
                  child: SingleChildScrollView(
                    padding: padding,
                    child: calendar,
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: SingleChildScrollView(
                    padding: padding,
                    child: dayList,
                  ),
                ),
              ],
            ),
          ),
        ),
      },
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '${date.month}/${date.day}（${weekdayLabel(date)}）的揪團',
          style: text.titleLarge,
        ),
        const SizedBox(height: AppSpacing.medium),
        if (groups.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Column(
                children: [
                  Text('這天還沒有人揪團', style: text.bodyLarge),
                  const SizedBox(height: AppSpacing.medium),
                  OutlinedButton.icon(
                    key: const Key('groups-empty-create'),
                    onPressed: () => openGroupForm(context, ref, date: date),
                    icon: const Icon(Icons.add),
                    label: const Text('我要開團'),
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
          OutlinedButton.icon(
            key: const Key('groups-day-create'),
            onPressed: () => openGroupForm(context, ref, date: date),
            icon: const Icon(Icons.add),
            label: const Text('我要揪團'),
          ),
      ],
    );
  }
}
