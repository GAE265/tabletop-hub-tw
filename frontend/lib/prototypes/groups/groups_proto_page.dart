import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../domains/groups/data/group.dart';
import '../../domains/groups/state/group_clock.dart';
import '../../domains/groups/state/group_form_state.dart';
import '../../domains/groups/state/groups_calendar_state.dart';
import 'group_detail_proto_page.dart';
import 'group_form_proto_page.dart';

/// 揪團月曆參考畫面：只用預設元件，不調顏色、字型、間距（AGENTS.md 5.4）。
class GroupsProtoPage extends ConsumerWidget {
  const GroupsProtoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    final notifier = ref.read(groupsCalendarProvider.notifier);
    return Scaffold(
      key: const Key('groups-proto-page'),
      appBar: AppBar(title: const Text('揪團月曆（參考畫面）')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => openGroupForm(context, ref, date: state.selectedDate),
        icon: const Icon(Icons.add),
        label: const Text('我要開團'),
      ),
      body: ListView(
        children: [
          Row(
            children: [
              IconButton(
                tooltip: '上個月',
                onPressed: notifier.previousMonth,
                icon: const Icon(Icons.chevron_left),
              ),
              Text('${state.month.year} 年 ${state.month.month} 月'),
              IconButton(
                tooltip: '下個月',
                onPressed: notifier.nextMonth,
                icon: const Icon(Icons.chevron_right),
              ),
              TextButton(
                onPressed: notifier.goToToday,
                child: const Text('今天'),
              ),
              const Spacer(),
              const _OrganizerFilter(),
            ],
          ),
          state.groups.when(
            skipLoadingOnRefresh: false,
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => Column(
              children: [
                Text(error is ApiException ? error.message : '發生未知錯誤'),
                ElevatedButton(
                  onPressed: notifier.reload,
                  child: const Text('重試'),
                ),
              ],
            ),
            data: (_) => const _CalendarGrid(),
          ),
          const Divider(),
          const _DayList(),
        ],
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
      builder: (_) => GroupFormProtoPage(initial: GroupFormData(date: date)),
    ),
  );
}

class _OrganizerFilter extends ConsumerWidget {
  const _OrganizerFilter();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final options = ref.watch(organizerOptionsProvider);
    final selected = ref.watch(
      groupsCalendarProvider.select((s) => s.organizerId),
    );
    return DropdownButton<String?>(
      value: options.any((o) => o.id == selected) ? selected : null,
      onChanged: ref.read(groupsCalendarProvider.notifier).setOrganizer,
      items: [
        const DropdownMenuItem(child: Text('全部開團主')),
        for (final option in options)
          DropdownMenuItem(
            value: option.id,
            child: Text('${option.name}（${option.count} 場）'),
          ),
      ],
    );
  }
}

class _CalendarGrid extends ConsumerWidget {
  const _CalendarGrid();

  static const _weekdays = ['日', '一', '二', '三', '四', '五', '六'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    final counts = ref.watch(calendarCountsProvider);
    final month = state.month;
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    // DateTime.weekday：週一 = 1 … 週日 = 7；月曆從週日開始
    final leading = month.weekday % 7;
    final cells = <Widget>[
      for (final name in _weekdays) Center(child: Text(name)),
      for (var i = 0; i < leading; i++) const SizedBox.shrink(),
      for (var day = 1; day <= daysInMonth; day++)
        _DayCell(
          date: DateTime(month.year, month.month, day),
          count: counts[DateTime(month.year, month.month, day)] ?? 0,
          selected:
              state.selectedDate == DateTime(month.year, month.month, day),
        ),
    ];
    return GridView.count(
      crossAxisCount: 7,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      children: cells,
    );
  }
}

class _DayCell extends ConsumerWidget {
  const _DayCell({
    required this.date,
    required this.count,
    required this.selected,
  });

  final DateTime date;
  final int count;
  final bool selected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    void select() => ref.read(groupsCalendarProvider.notifier).selectDate(date);
    final label = Column(
      mainAxisSize: MainAxisSize.min,
      children: [Text('${date.day}'), if (count > 0) Text('$count 團')],
    );
    return selected
        ? FilledButton.tonal(onPressed: select, child: label)
        : TextButton(onPressed: select, child: label);
  }
}

class _DayList extends ConsumerWidget {
  const _DayList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    if (state.groups.isLoading || state.groups.hasError) {
      return const SizedBox.shrink();
    }
    final date = state.selectedDate;
    final groups = ref.watch(selectedDayGroupsProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ListTile(title: Text('${date.month}/${date.day} 的揪團')),
        if (groups.isEmpty)
          ListTile(
            title: const Text('這天還沒有人揪團'),
            trailing: TextButton(
              onPressed: () => openGroupForm(context, ref, date: date),
              child: const Text('我要開團'),
            ),
          ),
        for (final group in groups) _GroupTile(group: group),
      ],
    );
  }
}

class _GroupTile extends ConsumerWidget {
  const _GroupTile({required this.group});

  final Group group;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final details = [
      formatTimeRange(clock, group),
      group.shop.name,
      '開團主：${group.organizer.displayName}',
      ?group.game?.name,
      ?feeLabel(group.fee),
    ];
    return ListTile(
      title: Text(group.title),
      subtitle: Text(details.join(' · ')),
      trailing: Text(groupSlotLabel(group)),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupDetailProtoPage(groupId: group.id),
        ),
      ),
    );
  }
}

String _two(int value) => value.toString().padLeft(2, '0');

/// 例如「13:00 – 15:00」（裝置時區）。
String formatTimeRange(GroupClock clock, Group group) {
  final start = clock.toLocal(group.startAt);
  final end = clock.toLocal(group.endAt);
  return '${_two(start.hour)}:${_two(start.minute)} – '
      '${_two(end.hour)}:${_two(end.minute)}';
}

/// 沒填寫時不顯示；0 元顯示「免費」。
String? feeLabel(int? fee) {
  if (fee == null) return null;
  return fee == 0 ? '免費' : '\$$fee／人';
}
