import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/group.dart';
import '../data/groups_repository.dart';
import 'current_user.dart';
import 'group_clock.dart';

/// 月曆一次載入的筆數上限（後端 page_size 最大 100）。
const calendarPageSize = 100;

/// 揪團月曆的狀態。月份與日期都是裝置時區的牆上時間。
class GroupsCalendarState {
  const GroupsCalendarState({
    required this.month,
    required this.selectedDate,
    required this.groups,
    this.organizerId,
  });

  /// 目前顯示的月份（該月 1 日）。
  final DateTime month;

  /// 目前選取的日期。
  final DateTime selectedDate;

  /// 依開團主篩選；null 為全部。
  final String? organizerId;

  /// 目前月份的所有揪團（未篩選）。
  final AsyncValue<List<Group>> groups;

  GroupsCalendarState copyWith({
    DateTime? month,
    DateTime? selectedDate,
    AsyncValue<List<Group>>? groups,
    String? Function()? organizerId,
  }) => GroupsCalendarState(
    month: month ?? this.month,
    selectedDate: selectedDate ?? this.selectedDate,
    groups: groups ?? this.groups,
    organizerId: organizerId == null ? this.organizerId : organizerId(),
  );
}

/// 今天（含）以後的日期才可以選；今天以前的格子停用，但照樣顯示團數。
bool isSelectableDate(DateTime date, DateTime today) =>
    !dateOnly(date).isBefore(dateOnly(today));

/// 月曆的操作：切換月份、選日期、篩選開團主、重新載入。
class GroupsCalendarNotifier extends Notifier<GroupsCalendarState> {
  Future<void> _pending = Future.value();
  int _requestId = 0;

  /// 最近一次載入完成的 Future（測試與畫面可以等待它）。
  Future<void> get loaded => _pending;

  GroupClock get _clock => ref.read(groupClockProvider);

  DateTime _today() => dateOnly(_clock.toLocal(_clock.now()));

  @override
  GroupsCalendarState build() {
    // 後端依目前使用者回傳 my_status；換人後要重新查詢，月份與選取的日期保留
    ref.listen(currentUserIdProvider, (previous, next) {
      if (previous != next) reload();
    });
    final today = _today();
    final month = DateTime(today.year, today.month);
    // build 期間不能改 state，所以排到下一個 microtask 才開始載入
    _pending = Future.microtask(() => _fetch(month));
    return GroupsCalendarState(
      month: month,
      selectedDate: today,
      groups: const AsyncLoading(),
    );
  }

  /// 依目前月份重新載入（例如報名、開團後）。
  void reload() => _load(state.month);

  void previousMonth() => _changeMonth(-1);

  void nextMonth() => _changeMonth(1);

  /// 「今天」按鈕：回到本月並選取今天。
  void goToToday() => goToDate(_today());

  /// 切到某天所在的月份並選取該天（開團成功後使用），一律重新載入。
  void goToDate(DateTime date) {
    final day = dateOnly(date);
    state = state.copyWith(selectedDate: day);
    _load(DateTime(day.year, day.month));
  }

  /// 選取某天；今天以前的日期不能選，選取維持不變。
  void selectDate(DateTime date) {
    if (!isSelectableDate(date, _today())) return;
    state = state.copyWith(selectedDate: dateOnly(date));
  }

  void setOrganizer(String? organizerId) =>
      state = state.copyWith(organizerId: () => organizerId);

  void _changeMonth(int delta) {
    final month = DateTime(state.month.year, state.month.month + delta);
    // 預設選 1 號；1 號已經過了而這個月包含今天時，改選今天
    final today = _today();
    final sameMonth = today.year == month.year && today.month == month.month;
    state = state.copyWith(
      selectedDate: sameMonth && month.isBefore(today) ? today : month,
    );
    _load(month);
  }

  void _load(DateTime month) {
    state = state.copyWith(month: month, groups: const AsyncLoading());
    _pending = _fetch(month);
  }

  Future<void> _fetch(DateTime month) async {
    final requestId = ++_requestId;
    final repo = ref.read(groupsRepositoryProvider);
    final from = _clock.fromLocal(month);
    final before = _clock.fromLocal(DateTime(month.year, month.month + 1));
    final result = await AsyncValue.guard(() async {
      final all = <Group>[];
      for (var page = 1; ; page++) {
        final result = await repo.list(
          startFrom: from,
          startBefore: before,
          page: page,
          pageSize: calendarPageSize,
        );
        all.addAll(result.items);
        if (result.items.isEmpty || all.length >= result.total) return all;
      }
    });
    // 切換月份很快時，只採用最後一次的結果
    if (requestId != _requestId || !ref.mounted) return;
    state = state.copyWith(groups: result);
  }
}

final groupsCalendarProvider =
    NotifierProvider<GroupsCalendarNotifier, GroupsCalendarState>(
      GroupsCalendarNotifier.new,
    );

/// 套用開團主篩選後的當月揪團；載入中或失敗時為空。
final _filteredGroupsProvider = Provider<List<Group>>((ref) {
  final state = ref.watch(groupsCalendarProvider);
  final groups = state.groups.isLoading ? null : state.groups.value;
  if (groups == null) return const [];
  final organizerId = state.organizerId;
  if (organizerId == null) return groups;
  return [
    for (final g in groups)
      if (g.organizer.id == organizerId) g,
  ];
});

/// 日期（牆上時間）→ 當天團數。
final calendarCountsProvider = Provider<Map<DateTime, int>>((ref) {
  final clock = ref.watch(groupClockProvider);
  final counts = <DateTime, int>{};
  for (final group in ref.watch(_filteredGroupsProvider)) {
    final day = dateOnly(clock.toLocal(group.startAt));
    counts[day] = (counts[day] ?? 0) + 1;
  }
  return counts;
});

/// 選取日期的揪團，依開始時間排序。
final selectedDayGroupsProvider = Provider<List<Group>>((ref) {
  final clock = ref.watch(groupClockProvider);
  final selected = ref.watch(groupsCalendarProvider).selectedDate;
  return [
    for (final group in ref.watch(_filteredGroupsProvider))
      if (dateOnly(clock.toLocal(group.startAt)) == selected) group,
  ]..sort((a, b) => a.startAt.compareTo(b.startAt));
});

/// 開團主篩選的選項。
class OrganizerOption {
  const OrganizerOption({
    required this.id,
    required this.name,
    required this.count,
  });

  final String id;
  final String name;

  /// 當月場數。
  final int count;
}

/// 當月出現過的開團主，依場數由多到少，同場數依名稱排序。
final organizerOptionsProvider = Provider<List<OrganizerOption>>((ref) {
  final state = ref.watch(groupsCalendarProvider);
  final groups = state.groups.isLoading ? null : state.groups.value;
  final byId = <String, (String, int)>{};
  for (final g in groups ?? const <Group>[]) {
    final current = byId[g.organizer.id];
    byId[g.organizer.id] = (g.organizer.displayName, (current?.$2 ?? 0) + 1);
  }
  return [
    for (final MapEntry(key: id, value: (name, count)) in byId.entries)
      OrganizerOption(id: id, name: name, count: count),
  ]..sort((a, b) {
    final byCount = b.count.compareTo(a.count);
    return byCount != 0 ? byCount : a.name.compareTo(b.name);
  });
});

/// 列表上的名額狀態文字。
String groupSlotLabel(Group group) {
  if (group.status == 'cancelled') return '已取消';
  if (group.status == 'ended') return '已結束';
  if (group.remainingSlots <= 0) return '已額滿，候補 ${group.waitlistCount} 人';
  return '剩 ${group.remainingSlots} 位';
}
