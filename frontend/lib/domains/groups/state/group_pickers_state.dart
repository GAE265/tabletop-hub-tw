import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/group.dart';
import '../data/groups_repository.dart';

/// 開團表單的店家選項（`GET /api/v1/shops`）。
/// 失敗不自動重試（Riverpod 3 預設會重試），交給畫面上的「重試」。
final shopOptionsProvider = FutureProvider.autoDispose<List<ShopRef>>(
  (ref) => ref.watch(groupsRepositoryProvider).listShops(),
  retry: (_, _) => null,
);

/// 開團表單的遊戲選項：全部遊戲，一次載入，搜尋時在本機篩選（[filterGames]）。
final gameOptionsProvider = FutureProvider.autoDispose<List<GameRef>>(
  (ref) => ref.watch(groupsRepositoryProvider).listGames(),
  retry: (_, _) => null,
);

/// 依名稱篩選遊戲：部分相符、英文不分大小寫；關鍵字是空白時全部列出。
List<GameRef> filterGames(List<GameRef> games, String query) {
  final keyword = query.trim().toLowerCase();
  if (keyword.isEmpty) return games;
  return [
    for (final game in games)
      if (game.name.toLowerCase().contains(keyword)) game,
  ];
}
