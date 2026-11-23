import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../state/group_clock.dart';
import '../../state/groups_calendar_state.dart';
import 'group_widgets.dart';

/// 月曆卡片：月份切換與每天的團數（開團主篩選在頁首，見 [OrganizerFilter]）。
class MonthCalendar extends ConsumerWidget {
  const MonthCalendar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupsCalendarProvider);
    final notifier = ref.read(groupsCalendarProvider.notifier);
    return ThickCard(
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
                  style: TextButton.styleFrom(
                    backgroundColor: AppColors.amberTint,
                    foregroundColor: AppColors.amberText,
                    shape: const StadiumBorder(),
                  ),
                  child: const Text('今天'),
                ),
              ],
            ),
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

/// 開團主篩選：「全部開團主」或某位開團主（N 場），月曆與當日列表都只算該開團主。
class OrganizerFilter extends ConsumerWidget {
  const OrganizerFilter({super.key});

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
                child: Center(
                  child: Text(
                    name,
                    // 週末用焦糖橘標出來
                    style: name == '日' || name == '六'
                        ? muted.copyWith(color: AppColors.primaryText)
                        : muted,
                  ),
                ),
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
                enabled: isSelectableDate(
                  DateTime(month.year, month.month, day),
                  today,
                ),
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
    required this.enabled,
  });

  final DateTime date;
  final int count;
  final bool selected;
  final bool isToday;

  /// 今天以前的日期停用：點了沒有反應，文字變淡，但照樣顯示團數。
  final bool enabled;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    final dayColor = selected
        ? scheme.onPrimary
        : enabled
        ? scheme.onSurface
        : AppColors.inkMuted;
    // 團數用膠囊：選取時白底橘字，其他是橘色淡底；已過的是灰字（格子本身灰底）
    final countColor = enabled ? AppColors.primaryText : AppColors.inkMuted;
    final countBackground = selected
        ? AppColors.surface
        : enabled
        ? AppColors.primaryTint
        : Colors.transparent;
    final radius = BorderRadius.circular(AppRadius.button);
    return Material(
      // 已過的揪團用灰底，和之後的揪團區別
      color: selected
          ? scheme.primary
          : count > 0 && !enabled
          ? AppColors.border
          : Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: isToday && !selected
            ? BorderSide(color: scheme.primary)
            : BorderSide.none,
      ),
      child: InkWell(
        borderRadius: radius,
        onTap: enabled
            ? () => ref.read(groupsCalendarProvider.notifier).selectDate(date)
            : null,
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
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: countBackground,
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.xSmall,
                      ),
                      child: Text(
                        '$count 團',
                        style: text.labelSmall!.copyWith(
                          color: countColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
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
