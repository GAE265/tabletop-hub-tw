import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/match_input.dart';
import '../data/matches_repository.dart';
import 'match_detail_state.dart';
import 'turn_form_state.dart' show overwritePromptText;

export 'turn_form_state.dart' show overwritePromptText;

/// 後端回 409 `MATCH_RESULT_ALREADY_RECORDED` 之後的待確認狀態。
///
/// [input] 是使用者剛輸入的內容；[existing] 是後端回傳的 details（`result` 是既有結果）。
class ResultOverwritePrompt {
  const ResultOverwritePrompt({required this.input, required this.existing});

  final ResultInput input;
  final Map<String, dynamic> existing;
}

/// 記錄結果的表單（陣營勝負）：獲勝陣營，以及每個座位的陣營。
class ResultFormState {
  const ResultFormState({
    this.winningFaction,
    this.factions = const {},
    this.busy = false,
    this.message,
    this.error,
    this.errors = const {},
    this.overwrite,
  });

  final String? winningFaction;

  /// 座位編號 → 陣營代碼。
  final Map<int, String> factions;
  final bool busy;
  final String? message;
  final ApiException? error;

  /// 欄位錯誤：鍵是 winningFaction、factions。
  final Map<String, String> errors;

  /// 不為 null 時，畫面要顯示 [overwritePromptText] 與確認、取消按鈕。
  final ResultOverwritePrompt? overwrite;

  ResultFormState copyWith({
    String? Function()? winningFaction,
    Map<int, String>? factions,
    bool? busy,
    String? Function()? message,
    ApiException? Function()? error,
    Map<String, String>? errors,
    ResultOverwritePrompt? Function()? overwrite,
  }) => ResultFormState(
    winningFaction: winningFaction == null
        ? this.winningFaction
        : winningFaction(),
    factions: factions ?? this.factions,
    busy: busy ?? this.busy,
    message: message == null ? this.message : message(),
    error: error == null ? this.error : error(),
    errors: errors ?? this.errors,
    overwrite: overwrite == null ? this.overwrite : overwrite(),
  );
}

class ResultFormNotifier extends Notifier<ResultFormState> {
  ResultFormNotifier(this.matchId);

  final String matchId;

  MatchesRepository get _repo => ref.read(matchesRepositoryProvider);

  @override
  ResultFormState build() => const ResultFormState();

  void setWinningFaction(String? code) =>
      state = state.copyWith(winningFaction: () => code);

  void setFaction(int seat, String code) =>
      state = state.copyWith(factions: {...state.factions, seat: code});

  /// 這局目前所有座位（從詳細資料取得）。
  List<int>? get _seats => ref
      .read(matchDetailProvider(matchId))
      .match
      .value
      ?.participants
      .map((p) => p.seatNumber)
      .toList();

  Future<void> submit() async {
    if (state.busy) return;
    final seats = _seats;
    if (seats == null) {
      state = state.copyWith(
        message: () => null,
        error: () => const ApiException(
          code: 'MATCH_NOT_LOADED',
          message: '還沒載入這一局，請先刷新',
        ),
      );
      return;
    }
    final missing = [
      for (final seat in seats)
        if (!state.factions.containsKey(seat)) seat,
    ];
    final errors = {
      if (state.winningFaction == null) 'winningFaction': '請選擇獲勝陣營',
      if (missing.isNotEmpty)
        'factions': '請為每個座位選擇陣營（缺 ${missing.join(', ')} 號）',
    };
    if (errors.isNotEmpty) {
      state = state.copyWith(
        errors: errors,
        message: () => null,
        error: () => null,
      );
      return;
    }
    await _send(
      ResultInput(
        winningFaction: state.winningFaction!,
        factions: {for (final seat in seats) seat: state.factions[seat]!},
      ),
      overwrite: false,
    );
  }

  /// 使用者確認要更新：帶 overwrite=true 重送剛才的內容（其他人的確認會被清除）。
  Future<void> confirmOverwrite() async {
    final prompt = state.overwrite;
    if (prompt == null || state.busy) return;
    await _send(prompt.input, overwrite: true);
  }

  void cancelOverwrite() => state = state.copyWith(overwrite: () => null);

  Future<void> _send(ResultInput input, {required bool overwrite}) async {
    state = state.copyWith(
      busy: true,
      errors: const {},
      message: () => null,
      error: () => null,
    );
    try {
      await _repo.recordResult(matchId, input, overwrite: overwrite);
      await ref.read(matchDetailProvider(matchId).notifier).reload();
      if (!ref.mounted) return;
      state = state.copyWith(
        message: () => overwrite ? '結果已更新' : '已記錄結果',
        overwrite: () => null,
      );
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      if (!overwrite && e.code == 'MATCH_RESULT_ALREADY_RECORDED') {
        state = state.copyWith(
          overwrite: () =>
              ResultOverwritePrompt(input: input, existing: e.details),
        );
      } else {
        state = state.copyWith(error: () => e, overwrite: () => null);
      }
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
  }
}

final resultFormProvider = NotifierProvider.autoDispose
    .family<ResultFormNotifier, ResultFormState, String>(
      ResultFormNotifier.new,
    );
