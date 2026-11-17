import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/group.dart';
import '../data/groups_repository.dart';

/// 開團表單的店家選項（`GET /api/v1/shops`）。
/// 失敗不自動重試（Riverpod 3 預設會重試），交給畫面上的「重試」。
final shopOptionsProvider = FutureProvider.autoDispose<List<ShopRef>>(
  (ref) => ref.watch(groupsRepositoryProvider).listShops(),
  retry: (_, _) => null,
);

/// 停止輸入多久之後才查詢，避免每打一個字就呼叫一次 API。
const gameSearchDelay = Duration(milliseconds: 300);

class GameSearchState {
  const GameSearchState({
    this.query = '',
    this.results = const AsyncData(<GameRef>[]),
  });

  final String query;
  final AsyncValue<List<GameRef>> results;
}

/// 開團表單的遊戲搜尋。結果不排除已選的遊戲，由畫面依目前已選的遊戲過濾。
class GameSearchNotifier extends Notifier<GameSearchState> {
  Timer? _timer;
  int _requestId = 0;

  @override
  GameSearchState build() {
    ref.onDispose(() => _timer?.cancel());
    return const GameSearchState();
  }

  /// 輸入關鍵字；停止輸入 [gameSearchDelay] 後才查詢，只查最後一次的關鍵字。
  void search(String query) {
    _timer?.cancel();
    final requestId = ++_requestId;
    if (query.trim().isEmpty) {
      state = GameSearchState(query: query);
      return;
    }
    state = GameSearchState(query: query, results: const AsyncLoading());
    _timer = Timer(gameSearchDelay, () => _fetch(query, requestId));
  }

  /// 清空關鍵字與結果（例如選好一款遊戲之後），等待中的查詢取消。
  void clear() {
    _timer?.cancel();
    _requestId++;
    state = const GameSearchState();
  }

  Future<void> _fetch(String query, int requestId) async {
    final results = await AsyncValue.guard(
      () => ref.read(groupsRepositoryProvider).searchGames(query.trim()),
    );
    // 查詢期間又輸入了新的關鍵字，就丟掉這次的結果
    if (!ref.mounted || requestId != _requestId) return;
    state = GameSearchState(query: query, results: results);
  }
}

final gameSearchProvider =
    NotifierProvider.autoDispose<GameSearchNotifier, GameSearchState>(
      GameSearchNotifier.new,
    );
