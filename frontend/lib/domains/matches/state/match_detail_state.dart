import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/game_match.dart';
import '../data/match_input.dart';
import '../data/matches_repository.dart';
import 'match_current_user.dart';

/// 一局的詳細畫面上可以出現的操作按鈕。
///
/// join＝自己加入；addNamed＝新增沒有帳號的人；leave＝自己退出；confirm＝確認紀錄。
/// 移除其他參加者的按鈕看 [MatchDetailState.canManageParticipants]。
enum MatchAction { join, addNamed, leave, confirm }

class MatchDetailState {
  const MatchDetailState({
    required this.match,
    this.refreshing = false,
    this.busy = false,
    this.message,
    this.error,
  });

  final AsyncValue<GameMatch> match;

  /// 刷新進行中；刷新期間仍保留上一次的內容，畫面不會閃成空白。
  final bool refreshing;

  /// 加入、新增、移除、確認進行中；畫面要停用按鈕並顯示載入中。
  final bool busy;

  /// 上一個操作成功的提示，例如「已加入這一局」。
  final String? message;

  /// 上一個操作失敗的錯誤（含後端的錯誤碼與 details）。
  final ApiException? error;

  MatchDetailState copyWith({
    AsyncValue<GameMatch>? match,
    bool? refreshing,
    bool? busy,
    String? Function()? message,
    ApiException? Function()? error,
  }) => MatchDetailState(
    match: match ?? this.match,
    refreshing: refreshing ?? this.refreshing,
    busy: busy ?? this.busy,
    message: message == null ? this.message : message(),
    error: error == null ? this.error : error(),
  );

  /// 「N 人參加、M 人有帳號、K 人已確認」；還沒載入時為 null。
  String? get participantSummary {
    final m = match.value;
    if (m == null) return null;
    return '${m.participantCount} 人參加、${m.accountCount} 人有帳號、'
        '${m.confirmedCount} 人已確認';
  }

  /// 是否已成為有效紀錄（已記錄結果，且有帳號的參加者都確認）。
  String? get validityLabel {
    final m = match.value;
    if (m == null) return null;
    return m.isValid ? '有效紀錄' : '尚未成為有效紀錄';
  }

  /// 目前使用者在這一局的參加者；不在這一局為 null。
  MatchParticipant? mine(String? userId) {
    final m = match.value;
    if (m == null || userId == null) return null;
    for (final participant in m.participants) {
      if (participant.userId == userId) return participant;
    }
    return null;
  }

  /// 進行中，而且我是參加者：可以新增、移除參加者。
  bool canManageParticipants(String? userId) =>
      match.value?.status == 'in_progress' && mine(userId) != null;

  /// 依這一局的狀態與目前使用者決定要顯示哪些按鈕。
  List<MatchAction> actionsFor(String? userId) {
    final m = match.value;
    if (m == null || userId == null) return const [];
    final me = mine(userId);
    if (m.status == 'in_progress') {
      return me == null
          ? const [MatchAction.join]
          : const [MatchAction.addNamed, MatchAction.leave];
    }
    return me != null && !me.isConfirmed
        ? const [MatchAction.confirm]
        : const [];
  }
}

/// 一局的狀態與操作（查詢、刷新、加入、新增、移除、確認）。
///
/// 記錄回合與結果是各自的表單狀態（turn_form_state、result_form_state），成功後會呼叫 [reload]。
class MatchDetailNotifier extends Notifier<MatchDetailState> {
  MatchDetailNotifier(this.matchId);

  final String matchId;
  Future<void> _pending = Future.value();

  /// 最近一次載入完成的 Future。
  Future<void> get loaded => _pending;

  MatchesRepository get _repo => ref.read(matchesRepositoryProvider);

  @override
  MatchDetailState build() {
    _pending = Future.microtask(_fetch);
    return const MatchDetailState(match: AsyncLoading());
  }

  /// 刷新：重新查詢這一局。其他人記錄的內容用這個取得（不做即時推送）。
  /// 重新載入期間仍保留上一次的內容（[MatchDetailState.refreshing] 為 true）。
  Future<void> reload() {
    state = state.copyWith(refreshing: true);
    return _pending = _fetch();
  }

  Future<void> _fetch() async {
    final match = await AsyncValue.guard(() => _repo.get(matchId));
    if (!ref.mounted) return;
    state = state.copyWith(match: match, refreshing: false);
  }

  /// 自己加入這一局，座位不選就給最小的空位。
  Future<void> joinSelf({int? seatNumber}) => _run('已加入這一局', () async {
    await _repo.addParticipant(
      matchId,
      ParticipantInput(seatNumber: seatNumber),
    );
  });

  /// 新增沒有帳號的參加者（只有名字，例如 Amy）。
  Future<void> addNamed(String name, {int? seatNumber}) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) {
      state = state.copyWith(
        message: () => null,
        error: () => const ApiException(code: 'EMPTY_NAME', message: '請輸入名字'),
      );
      return;
    }
    await _run(
      '已新增 $trimmed',
      () async => _repo.addParticipant(
        matchId,
        ParticipantInput(displayName: trimmed, seatNumber: seatNumber),
      ),
    );
  }

  /// 移除參加者（退出，或移除沒有帳號的人與其他參加者）。畫面要先跳確認對話框。
  /// 座位已出現在任何回合時後端回 409 `MATCH_PARTICIPANT_HAS_TURNS`，錯誤的 details 帶回合編號。
  Future<void> remove(String participantId) => _run('已移除參加者', () async {
    await _repo.removeParticipant(matchId, participantId);
  });

  /// 確認自己的紀錄（已記錄結果之後才能確認）。
  Future<void> confirmMine() async {
    final me = state.mine(ref.read(matchUserIdProvider));
    if (me == null) {
      state = state.copyWith(
        message: () => null,
        error: () => const ApiException(
          code: 'NOT_A_PARTICIPANT',
          message: '你不是這一局的參加者，不能確認',
        ),
      );
      return;
    }
    await _run('已確認', () async {
      await _repo.confirm(matchId, me.id);
    });
  }

  /// 執行一個操作：進行中不接受重複送出；成功後重新載入這一局。
  Future<void> _run(
    String successMessage,
    Future<void> Function() action,
  ) async {
    if (state.busy) return;
    state = state.copyWith(busy: true, message: () => null, error: () => null);
    try {
      await action();
      await _fetch();
      if (!ref.mounted) return;
      state = state.copyWith(message: () => successMessage);
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      state = state.copyWith(error: () => e);
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
  }
}

final matchDetailProvider = NotifierProvider.autoDispose
    .family<MatchDetailNotifier, MatchDetailState, String>(
      MatchDetailNotifier.new,
    );
