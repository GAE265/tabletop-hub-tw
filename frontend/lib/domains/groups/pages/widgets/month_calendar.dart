import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../state/group_clock.dart';
import '../../state/groups_calendar_state.dart';
import 'group_widgets.dart';

/// 月曆卡片：月份切換、開團主篩選，以及每天的團數。
class MonthCalendar extends ConsumerWidget {
  const MonthCalendar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    final notifier = ref.read(groupsCalendarProvider.notifier);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                IconButton(
                  tooltip: '上個月',
                  onPressed: notifier.previousMonth,
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: Text(
                    '${state.month.year} 年 ${state.month.month} 月',
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  tooltip: '下個月',
                  onPressed: notifier.nextMonth,
                  icon: const Icon(Icons.chevron_right),
                ),
                TextButton(
                  onPressed: notifier.goToToday,
                  child: const Text('今天'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            const _OrganizerFilter(),
            const SizedBox(height: AppSpacing.medium),
            state.groups.when(
              skipLoadingOnRefresh: false,
              loading: () => const LoadingIndicator(),
              error: (error, _) =>
                  LoadError(error: error, onRetry: notifier.reload),
              data: (_) => const _CalendarGrid(),
            ),
          ],
        ),
      ),
    );
  }
}

class _OrganizerFilter extends ConsumerWidget {
  const _OrganizerFilter();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final options = ref.watch(organizerOptionsProvider);
    final selected = ref.watch(
      groupsCalendarProvider.select((s) => s.organizerId),
    );
    return InputDecorator(
      decoration: const InputDecoration(
        labelText: '開團主',
        prefixIcon: Icon(Icons.person_search_outlined),
        contentPadding: EdgeInsets.symmetric(horizontal: AppSpacing.medium),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String?>(
          isExpanded: true,
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
        ),
      ),
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
    final clock = ref.watch(groupClockProvider);
    final today = dateOnly(clock.toLocal(clock.now()));
    final month = state.month;
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    // DateTime.weekday：週一 = 1 … 週日 = 7；月曆從週日開始
    final leading = month.weekday % 7;
    final muted = Theme.of(context).textTheme.labelMedium!.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    return Column(
      children: [
        Row(
          children: [
            for (final name in _weekdays)
              Expanded(
                child: Center(child: Text(name, style: muted)),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.small),
        GridView.count(
          crossAxisCount: 7,
          shrinkWrap: true,
          mainAxisSpacing: AppSpacing.xSmall,
          crossAxisSpacing: AppSpacing.xSmall,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            for (var i = 0; i < leading; i++) const SizedBox.shrink(),
            for (var day = 1; day <= daysInMonth; day++)
              _DayCell(
                date: DateTime(month.year, month.month, day),
                count: counts[DateTime(month.year, month.month, day)] ?? 0,
                selected:
                    state.selectedDate ==
                    DateTime(month.year, month.month, day),
                isToday: today == DateTime(month.year, month.month, day),
              ),
          ],
        ),
      ],
    );
  }
}

/// 一天的格子：選取時填滿主色，今天加上主色外框，有揪團時顯示團數。
class _DayCell extends ConsumerWidget {
  const _DayCell({
    required this.date,
    required this.count,
    required this.selected,
    required this.isToday,
  });

  final DateTime date;
  final int count;
  final bool selected;
  final bool isToday;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    final dayColor = selected ? scheme.onPrimary : scheme.onSurface;
    final countColor = selected ? scheme.onPrimary : scheme.onPrimaryContainer;
    final radius = BorderRadius.circular(AppRadius.button);
    return Material(
      color: selected
          ? scheme.primary
          : count > 0
          ? scheme.primaryContainer
          : Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: isToday && !selected
            ? BorderSide(color: scheme.primary)
            : BorderSide.none,
      ),
      child: InkWell(
        borderRadius: radius,
        onTap: () => ref.read(groupsCalendarProvider.notifier).selectDate(date),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xSmall),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '${date.day}',
                  style: text.bodyMedium!.copyWith(
                    color: dayColor,
                    fontWeight: selected || isToday ? FontWeight.w700 : null,
                  ),
                ),
                if (count > 0)
                  Text(
                    '$count 團',
                    style: text.labelSmall!.copyWith(
                      color: countColor,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
