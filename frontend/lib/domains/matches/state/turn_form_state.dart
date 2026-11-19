import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/match_input.dart';
import '../data/matches_repository.dart';
import 'match_detail_state.dart';

/// 同一回合已有紀錄時，請使用者確認的提示文字。
const overwritePromptText = '已經有人記錄了，要更新嗎？';

/// 白薔薇一個回合要記錄的四種數量。
enum TurnCounter { doubleBlade, darkBlade, giantBlade, faithful }

/// 後端回 409 `MATCH_TURN_ALREADY_RECORDED` 之後的待確認狀態。
///
/// [input] 是使用者剛輸入的內容（確認後原封不動帶 overwrite=true 重送）；
/// [existing] 是後端回傳的既有紀錄（turn_number、seat_number、game_data、recorded_by）。
class TurnOverwritePrompt {
  const TurnOverwritePrompt({required this.input, required this.existing});

  final TurnInput input;
  final Map<String, dynamic> existing;
}

/// 記錄回合的表單（白薔薇）：第幾回合、本回合首家（選填）、點選出牌的座位、四種數量、有沒有白薔薇。
class TurnFormState {
  const TurnFormState({
    this.turnNumber = 1,
    this.firstSeat,
    this.playedSeats = const {},
    this.doubleBladeCount = 0,
    this.darkBladeCount = 0,
    this.giantBladeCount = 0,
    this.faithfulCount = 0,
    this.hasWhiteRose = false,
    this.busy = false,
    this.message,
    this.error,
    this.errors = const {},
    this.overwrite,
  });

  final int turnNumber;

  /// 本回合首家的座位；選填，預設不選。
  final int? firstSeat;

  /// 這回合出牌的座位。
  final Set<int> playedSeats;
  final int doubleBladeCount;
  final int darkBladeCount;
  final int giantBladeCount;
  final int faithfulCount;
  final bool hasWhiteRose;
  final bool busy;

  /// 上一次送出成功的提示，例如「第 1 回合已記錄」。
  final String? message;

  /// 後端回的錯誤（不含「已有紀錄」，那個走 [overwrite]）。
  final ApiException? error;

  /// 欄位錯誤：鍵是 turnNumber、playedSeats。
  final Map<String, String> errors;

  /// 不為 null 時，畫面要顯示 [overwritePromptText] 與確認、取消按鈕。
  final TurnOverwritePrompt? overwrite;

  int count(TurnCounter counter) => switch (counter) {
    TurnCounter.doubleBlade => doubleBladeCount,
    TurnCounter.darkBlade => darkBladeCount,
    TurnCounter.giantBlade => giantBladeCount,
    TurnCounter.faithful => faithfulCount,
  };

  TurnFormState copyWith({
    int? turnNumber,
    int? Function()? firstSeat,
    Set<int>? playedSeats,
    int? doubleBladeCount,
    int? darkBladeCount,
    int? giantBladeCount,
    int? faithfulCount,
    bool? hasWhiteRose,
    bool? busy,
    String? Function()? message,
    ApiException? Function()? error,
    Map<String, String>? errors,
    TurnOverwritePrompt? Function()? overwrite,
  }) => TurnFormState(
    turnNumber: turnNumber ?? this.turnNumber,
    firstSeat: firstSeat == null ? this.firstSeat : firstSeat(),
    playedSeats: playedSeats ?? this.playedSeats,
    doubleBladeCount: doubleBladeCount ?? this.doubleBladeCount,
    darkBladeCount: darkBladeCount ?? this.darkBladeCount,
    giantBladeCount: giantBladeCount ?? this.giantBladeCount,
    faithfulCount: faithfulCount ?? this.faithfulCount,
    hasWhiteRose: hasWhiteRose ?? this.hasWhiteRose,
    busy: busy ?? this.busy,
    message: message == null ? this.message : message(),
    error: error == null ? this.error : error(),
    errors: errors ?? this.errors,
    overwrite: overwrite == null ? this.overwrite : overwrite(),
  );
}

class TurnFormNotifier extends Notifier<TurnFormState> {
  TurnFormNotifier(this.matchId);

  final String matchId;

  MatchesRepository get _repo => ref.read(matchesRepositoryProvider);

  @override
  TurnFormState build() => const TurnFormState();

  void setTurnNumber(int value) => state = state.copyWith(turnNumber: value);

  /// 設定本回合首家；傳 null 代表不選。
  void setFirstSeat(int? value) =>
      state = state.copyWith(firstSeat: () => value);

  /// 點選／取消點選出牌的座位。
  void togglePlayedSeat(int seat) {
    final seats = {...state.playedSeats};
    if (!seats.add(seat)) seats.remove(seat);
    state = state.copyWith(playedSeats: seats);
  }

  /// 設定數量，小於 0 一律當 0。
  void setCount(TurnCounter counter, int value) {
    final count = math.max(0, value);
    state = switch (counter) {
      TurnCounter.doubleBlade => state.copyWith(doubleBladeCount: count),
      TurnCounter.darkBlade => state.copyWith(darkBladeCount: count),
      TurnCounter.giantBlade => state.copyWith(giantBladeCount: count),
      TurnCounter.faithful => state.copyWith(faithfulCount: count),
    };
  }

  void setHasWhiteRose(bool value) =>
      state = state.copyWith(hasWhiteRose: value);

  Map<String, String> _validate() => {
    if (state.turnNumber < 1) 'turnNumber': '回合編號要從 1 開始',
    if (state.playedSeats.isEmpty) 'playedSeats': '請至少選一個出牌的座位',
  };

  TurnInput _buildInput() => TurnInput(
    turnNumber: state.turnNumber,
    seatNumber: state.firstSeat,
    gameData: WhiteRoseTurnData(
      playedSeatNumbers: state.playedSeats.toList()..sort(),
      doubleBladeCount: state.doubleBladeCount,
      darkBladeCount: state.darkBladeCount,
      giantBladeCount: state.giantBladeCount,
      faithfulCount: state.faithfulCount,
      hasWhiteRose: state.hasWhiteRose,
    ).toJson(),
  );

  /// 送出。同一回合已有紀錄時不會覆蓋，而是進入待確認狀態（[TurnFormState.overwrite]）。
  Future<void> submit() async {
    if (state.busy) return;
    final errors = _validate();
    if (errors.isNotEmpty) {
      state = state.copyWith(
        errors: errors,
        message: () => null,
        error: () => null,
      );
      return;
    }
    await _send(_buildInput(), overwrite: false);
  }

  /// 使用者確認要更新：帶 overwrite=true 重送剛才的內容。
  Future<void> confirmOverwrite() async {
    final prompt = state.overwrite;
    if (prompt == null || state.busy) return;
    await _send(prompt.input, overwrite: true);
  }

  /// 使用者不要更新：清除提示，舊紀錄不動。
  void cancelOverwrite() => state = state.copyWith(overwrite: () => null);

  Future<void> _send(TurnInput input, {required bool overwrite}) async {
    state = state.copyWith(
      busy: true,
      errors: const {},
      message: () => null,
      error: () => null,
    );
    try {
      final saved = await _repo.recordTurn(
        matchId,
        input,
        overwrite: overwrite,
      );
      final detail = ref.read(matchDetailProvider(matchId).notifier);
      await detail.reload();
      if (!ref.mounted) return;
      final recorded =
          ref
              .read(matchDetailProvider(matchId))
              .match
              .value
              ?.turns
              .map((t) => t.turnNumber) ??
          const <int>[];
      final next = recorded.fold(input.turnNumber, math.max) + 1;
      // 這個回合記好了：清空表單，準備記下一個回合
      state = TurnFormState(
        turnNumber: next,
        message: overwrite && !saved.created
            ? '第 ${input.turnNumber} 回合已更新'
            : '第 ${input.turnNumber} 回合已記錄',
      );
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      if (!overwrite && e.code == 'MATCH_TURN_ALREADY_RECORDED') {
        state = state.copyWith(
          overwrite: () => TurnOverwritePrompt(
            input: input,
            existing:
                (e.details['existing'] as Map?)?.cast<String, dynamic>() ??
                const {},
          ),
        );
      } else {
        state = state.copyWith(error: () => e, overwrite: () => null);
      }
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
  }
}

final turnFormProvider = NotifierProvider.autoDispose
    .family<TurnFormNotifier, TurnFormState, String>(TurnFormNotifier.new);
