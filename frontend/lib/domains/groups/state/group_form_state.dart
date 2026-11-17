import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/group.dart';
import '../data/group_input.dart';
import '../data/groups_repository.dart';
import 'group_clock.dart';
import 'group_detail_state.dart';
import 'groups_calendar_state.dart';

/// 開團／編輯表單的輸入。時間是裝置時區的牆上時間；數字欄位保留原始文字，驗證時才轉換。
class GroupFormData {
  const GroupFormData({
    this.shopId = '',
    this.title = '',
    this.date,
    this.startTime,
    this.endTime,
    this.capacity = '',
    this.fee = '',
    this.games = const [],
    this.description = '',
  });

  /// 編輯時帶入現有的值。
  factory GroupFormData.fromGroup(Group group, GroupClock clock) {
    final start = clock.toLocal(group.startAt);
    final end = clock.toLocal(group.endAt);
    return GroupFormData(
      shopId: group.shop.id,
      title: group.title,
      date: dateOnly(start),
      startTime: Duration(hours: start.hour, minutes: start.minute),
      endTime: Duration(hours: end.hour, minutes: end.minute),
      capacity: '${group.capacity}',
      fee: group.fee == null ? '' : '${group.fee}',
      games: group.games,
      description: group.description ?? '',
    );
  }

  final String shopId;
  final String title;
  final DateTime? date;

  /// 從當天 00:00 起算的時間。
  final Duration? startTime;
  final Duration? endTime;
  final String capacity;
  final String fee;

  /// 選好的遊戲，依選擇的順序。
  final List<GameRef> games;
  final String description;

  GroupFormData copyWith({
    String? shopId,
    String? title,
    DateTime? date,
    Duration? startTime,
    Duration? endTime,
    String? capacity,
    String? fee,
    List<GameRef>? games,
    String? description,
  }) => GroupFormData(
    shopId: shopId ?? this.shopId,
    title: title ?? this.title,
    date: date ?? this.date,
    startTime: startTime ?? this.startTime,
    endTime: endTime ?? this.endTime,
    capacity: capacity ?? this.capacity,
    fee: fee ?? this.fee,
    games: games ?? this.games,
    description: description ?? this.description,
  );
}

/// 前端先檢查一次，避免明顯錯誤還要等後端回 422。回傳「欄位 → 錯誤訊息」，沒有錯誤時為空。
Map<String, String> validateGroupForm(GroupFormData data) {
  final errors = <String, String>{};
  if (data.shopId.trim().isEmpty) errors['shopId'] = '請選擇店家';
  if (data.title.trim().isEmpty) errors['title'] = '請填寫標題';
  if (data.date == null) errors['date'] = '請選擇日期';
  if (data.startTime == null) errors['startTime'] = '請選擇開始時間';
  if (data.endTime == null) {
    errors['endTime'] = '請選擇結束時間';
  } else if (data.startTime != null && data.endTime! <= data.startTime!) {
    errors['endTime'] = '結束時間要晚於開始時間';
  }
  final capacity = int.tryParse(data.capacity.trim());
  if (capacity == null || capacity < 2) errors['capacity'] = '人數上限至少 2 人';
  if (data.fee.trim().isNotEmpty) {
    final fee = int.tryParse(data.fee.trim());
    if (fee == null || fee < 0) errors['fee'] = '費用要是 0 以上的整數';
  }
  return errors;
}

class GroupFormState {
  const GroupFormState({
    this.submitting = false,
    this.fieldErrors = const {},
    this.error,
  });

  final bool submitting;
  final Map<String, String> fieldErrors;

  /// 後端回傳的錯誤訊息。
  final String? error;
}

class GroupFormNotifier extends Notifier<GroupFormState> {
  @override
  GroupFormState build() => const GroupFormState();

  /// 開團（[groupId] 為 null）或編輯。成功回傳揪團，失敗回傳 null 並把錯誤放進 state。
  Future<Group?> submit(GroupFormData data, {String? groupId}) async {
    if (state.submitting) return null;
    final errors = validateGroupForm(data);
    if (errors.isNotEmpty) {
      state = GroupFormState(fieldErrors: errors);
      return null;
    }
    state = const GroupFormState(submitting: true);

    final clock = ref.read(groupClockProvider);
    final day = data.date!;
    final input = GroupInput(
      shopId: data.shopId.trim(),
      title: data.title.trim(),
      startAt: clock.fromLocal(day.add(data.startTime!)),
      endAt: clock.fromLocal(day.add(data.endTime!)),
      capacity: int.parse(data.capacity.trim()),
      fee: int.tryParse(data.fee.trim()),
      gameIds: [for (final game in data.games) game.id],
      description: data.description.trim().isEmpty
          ? null
          : data.description.trim(),
    );

    try {
      final repo = ref.read(groupsRepositoryProvider);
      final group = groupId == null
          ? await repo.create(input)
          : await repo.update(groupId, input.toUpdateJson());
      if (!ref.mounted) return group;
      state = const GroupFormState();
      // 月曆跳到該日並重新載入，新揪團才會出現
      ref.read(groupsCalendarProvider.notifier).goToDate(day);
      if (groupId != null && ref.exists(groupDetailProvider(groupId))) {
        await ref.read(groupDetailProvider(groupId).notifier).reload();
      }
      return group;
    } on ApiException catch (e) {
      if (ref.mounted) state = GroupFormState(error: e.message);
      return null;
    }
  }

  /// 開啟表單時清掉上一次的錯誤。
  void reset() => state = const GroupFormState();
}

final groupFormProvider = NotifierProvider<GroupFormNotifier, GroupFormState>(
  GroupFormNotifier.new,
);
