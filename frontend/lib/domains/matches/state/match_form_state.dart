import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/game_match.dart';
import '../data/match_input.dart';
import '../data/matches_repository.dart';

/// 開局表單：選遊戲、日期、店家或自家、自己的座位。
class MatchFormState {
  const MatchFormState({
    this.gameId,
    this.playedOn,
    this.locationType = 'home',
    this.shopId = '',
    this.seatNumber,
    this.busy = false,
    this.errors = const {},
    this.error,
    this.created,
  });

  final int? gameId;
  final DateTime? playedOn;

  /// `shop`（桌遊店）或 `home`（自家）。
  final String locationType;
  final String shopId;

  /// 自己的座位；沒填時後端給最小的空位。
  final int? seatNumber;
  final bool busy;

  /// 欄位的錯誤：鍵是欄位名（gameId、playedOn、shopId），值是要顯示的訊息。
  final Map<String, String> errors;

  /// 後端回的錯誤。
  final ApiException? error;

  /// 開局成功後的那一局；畫面據此跳到這一局的詳細畫面。
  final GameMatch? created;

  MatchFormState copyWith({
    int? Function()? gameId,
    DateTime? playedOn,
    String? locationType,
    String? shopId,
    int? Function()? seatNumber,
    bool? busy,
    Map<String, String>? errors,
    ApiException? Function()? error,
    GameMatch? Function()? created,
  }) => MatchFormState(
    gameId: gameId == null ? this.gameId : gameId(),
    playedOn: playedOn ?? this.playedOn,
    locationType: locationType ?? this.locationType,
    shopId: shopId ?? this.shopId,
    seatNumber: seatNumber == null ? this.seatNumber : seatNumber(),
    busy: busy ?? this.busy,
    errors: errors ?? this.errors,
    error: error == null ? this.error : error(),
    created: created == null ? this.created : created(),
  );
}

class MatchFormNotifier extends Notifier<MatchFormState> {
  MatchesRepository get _repo => ref.read(matchesRepositoryProvider);

  @override
  MatchFormState build() => const MatchFormState();

  void setGameId(int? value) => state = state.copyWith(gameId: () => value);

  void setPlayedOn(DateTime value) => state = state.copyWith(playedOn: value);

  /// 改成自家時，清掉已選的店家。
  void setLocationType(String value) => state = state.copyWith(
    locationType: value,
    shopId: value == 'home' ? '' : null,
  );

  void setShopId(String value) => state = state.copyWith(shopId: value);

  void setSeatNumber(int? value) =>
      state = state.copyWith(seatNumber: () => value);

  Map<String, String> _validate() => {
    if (state.gameId == null) 'gameId': '請選擇遊戲',
    if (state.playedOn == null) 'playedOn': '請選擇日期',
    if (state.locationType == 'shop' && state.shopId.trim().isEmpty)
      'shopId': '請選擇店家',
  };

  Future<void> submit() async {
    if (state.busy) return;
    final errors = _validate();
    if (errors.isNotEmpty) {
      state = state.copyWith(errors: errors, error: () => null);
      return;
    }
    state = state.copyWith(busy: true, errors: const {}, error: () => null);
    try {
      final created = await _repo.create(
        MatchInput(
          gameId: state.gameId!,
          playedOn: state.playedOn!,
          locationType: state.locationType,
          shopId: state.locationType == 'shop' ? state.shopId.trim() : null,
          seatNumber: state.seatNumber,
        ),
      );
      if (!ref.mounted) return;
      state = state.copyWith(created: () => created);
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      state = state.copyWith(error: () => e);
    } finally {
      if (ref.mounted) state = state.copyWith(busy: false);
    }
  }
}

final matchFormProvider =
    NotifierProvider.autoDispose<MatchFormNotifier, MatchFormState>(
      MatchFormNotifier.new,
    );
