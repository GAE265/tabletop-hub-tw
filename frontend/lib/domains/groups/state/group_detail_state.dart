import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/group.dart';
import '../data/groups_repository.dart';
import 'current_user.dart';
import 'groups_calendar_state.dart';

/// 揪團詳細畫面上可以出現的操作按鈕。
/// 揪團詳細頁的操作；`book` 是開團主替揪團訂位（跳到帶好揪團資料的訂位頁），
/// `recordMatch` 是開團主與成員填入戰績（跳到帶好揪團資料的戰績頁）。
/// `confirm` 是開團主確定成團（add-groups-notifications）。
enum GroupAction {
  join,
  joinWaitlist,
  leave,
  edit,
  book,
  recordMatch,
  confirm,
  cancel,
}

class GroupDetailState {
  const GroupDetailState({
    required this.group,
    this.members = const [],
    this.busy = false,
    this.message,
    this.error,
  });

  final AsyncValue<Group> group;
  final List<GroupMember> members;

  /// 報名、退出、取消進行中；畫面要停用按鈕並顯示載入中。
  final bool busy;

  /// 上一個操作成功的提示，例如「報名成功」。
  final String? message;

  /// 上一個操作失敗的訊息（後端錯誤的 message）。
  final String? error;

  GroupDetailState copyWith({
    AsyncValue<Group>? group,
    List<GroupMember>? members,
    bool? busy,
    String? Function()? message,
    String? Function()? error,
  }) => GroupDetailState(
    group: group ?? this.group,
    members: members ?? this.members,
    busy: busy ?? this.busy,
    message: message == null ? this.message : message(),
    error: error == null ? this.error : error(),
  );

  /// 依揪團狀態與目前使用者決定要顯示哪些按鈕。
  List<GroupAction> actionsFor(String? userId) {
    final g = group.value;
    if (g == null || g.status == 'cancelled') return const [];
    final isOrganizer = userId != null && g.organizer.id == userId;
    // 開團主與成員可以填入戰績（候補不行）；揪團結束後只剩這個按鈕
    final canRecord = isOrganizer || g.myStatus == 'member';
    if (g.status != 'open') {
      return canRecord ? const [GroupAction.recordMatch] : const [];
    }
    if (isOrganizer) {
      return [
        GroupAction.edit,
        GroupAction.book,
        GroupAction.recordMatch,
        // 還沒成團時才可以確定成團；成團後不能取消成團
        if (g.confirmedAt == null) GroupAction.confirm,
        GroupAction.cancel,
      ];
    }
    if (g.myStatus == 'member') {
      return const [GroupAction.leave, GroupAction.recordMatch];
    }
    if (g.myStatus != null) return const [GroupAction.leave];
    return g.remainingSlots > 0
        ? const [GroupAction.join]
        : const [GroupAction.joinWaitlist];
  }
}

/// 單一揪團的狀態與操作（報名、退出、取消）。
class GroupDetailNotifier extends Notifier<GroupDetailState> {
  GroupDetailNotifier(this.groupId);

  final String groupId;
  Future<void> _pending = Future.value();

  /// 最近一次載入完成的 Future。
  Future<void> get loaded => _pending;

  GroupsRepository get _repo => ref.read(groupsRepositoryProvider);

  @override
  GroupDetailState build() {
    // 報名狀態與按鈕依目前使用者而定；換人後要重新載入
    ref.listen(currentUserIdProvider, (previous, next) {
      if (previous != next) reload();
    });
    _pending = Future.microtask(_fetch);
    return const GroupDetailState(group: AsyncLoading());
  }

  Future<void> reload() {
    state = state.copyWith(group: const AsyncLoading());
    return _pending = _fetch();
  }

  Future<void> _fetch() async {
    final group = await AsyncValue.guard(() => _repo.get(groupId));
    final members = group.hasError
        ? const <GroupMember>[]
        : await _repo.listMembers(groupId).catchError((_) => <GroupMember>[]);
    if (!ref.mounted) return;
    state = state.copyWith(group: group, members: members);
  }

  /// 報名；額滿時後端會自動放進候補。
  Future<void> join() => _run(() async {
    final result = await _repo.join(groupId);
    return result.status == 'waitlisted'
        ? '已加入候補，目前第 ${result.waitlistPosition} 位'
        : '報名成功';
  });

  /// 自己退出（成員或候補）。畫面要先跳確認對話框。
  Future<void> leave() => _run(() async {
    final userId = ref.read(currentUserIdProvider);
    if (userId == null) {
      throw const ApiException(code: 'NO_CURRENT_USER', message: '無法取得目前使用者');
    }
    await _repo.removeMember(groupId, userId);
    return '已退出揪團';
  });

  /// 開團主確定成團，後端會通知所有成員。畫面要先跳確認對話框。
  Future<void> confirm() => _run(() async {
    await _repo.update(groupId, {'confirmed': true});
    return '已確定成團，已通知所有成員';
  });

  /// 開團主取消揪團。畫面要先跳確認對話框。
  Future<void> cancel() => _run(() async {
    await _repo.update(groupId, {'status': 'cancelled'});
    return '已取消揪團';
  });

  /// 執行一個操作：進行中不接受重複送出；成功後重新載入揪團與月曆。
  Future<void> _run(Future<String> Function() action) async {
    if (state.busy) return;
    state = state.copyWith(busy: true, message: () => null, error: () => null);
    try {
      final message = await action();
      await _fetch();
      if (!ref.mounted) return;
      state = state.copyWith(message: () => message);
      ref.read(groupsCalendarProvider.notifier).reload();
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      state = state.copyWith(error: () => e.message);
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
  }
}

final groupDetailProvider = NotifierProvider.autoDispose
    .family<GroupDetailNotifier, GroupDetailState, String>(
      GroupDetailNotifier.new,
    );
