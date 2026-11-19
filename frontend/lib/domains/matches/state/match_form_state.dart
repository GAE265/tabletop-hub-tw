import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../groups/data/group.dart';
import '../../groups/data/groups_repository.dart';
import '../../groups/state/group_clock.dart';
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
    this.groupId,
    this.group,
    this.groupLoading = false,
    this.groupError,
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

  /// 從揪團開局時的揪團 id（開局時帶 `group_id`，這一局連到該揪團）；不是從揪團來的為 null。
  final String? groupId;

  /// 從揪團進來時讀到的揪團（畫面上方顯示名稱）；還沒讀到或讀取失敗為 null。
  final Group? group;
  final bool groupLoading;

  /// 讀取揪團失敗的錯誤；這時 [groupId] 是 null，開局不會帶 `group_id`。
  final ApiException? groupError;
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
    String? Function()? groupId,
    Group? Function()? group,
    bool? groupLoading,
    ApiException? Function()? groupError,
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
    groupId: groupId == null ? this.groupId : groupId(),
    group: group == null ? this.group : group(),
    groupLoading: groupLoading ?? this.groupLoading,
    groupError: groupError == null ? this.groupError : groupError(),
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

  /// 從揪團的「填入戰績」進來時設定，開局時帶 `group_id`。
  void setGroupId(String? value) =>
      state = state.copyWith(groupId: () => value);

  /// 從揪團的「填入戰績」進來：讀取揪團並帶入。
  ///
  /// 成功：記下揪團與 `group_id`，地點改成桌遊店並選好揪團的店家，日期用揪團開始時間的
  /// 牆上日期；揪團剛好只選一款遊戲時，遊戲也自動選好（0 款或 2 款以上由使用者自己選）。
  /// 失敗：記下錯誤、不帶 `group_id`，表單其餘部分照常可用，可再呼叫一次重試。
  Future<void> loadGroup(String id) async {
    state = state.copyWith(groupLoading: true, groupError: () => null);
    try {
      final group = await ref.read(groupsRepositoryProvider).get(id);
      if (!ref.mounted) return;
      final start = ref.read(groupClockProvider).toLocal(group.startAt);
      state = state.copyWith(
        group: () => group,
        groupId: () => group.id,
        locationType: 'shop',
        shopId: group.shop.id,
        gameId: group.games.length == 1 ? () => group.games.single.id : null,
        playedOn: DateTime(start.year, start.month, start.day),
        groupLoading: false,
      );
    } on ApiException catch (e) {
      if (!ref.mounted) return;
      state = state.copyWith(
        group: () => null,
        groupId: () => null,
        groupError: () => e,
        groupLoading: false,
      );
    }
  }

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
          groupId: state.groupId,
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
