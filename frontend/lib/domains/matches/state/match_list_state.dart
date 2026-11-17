import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/game_match.dart';
import '../data/matches_repository.dart';

/// 最近的局（依日期由新到舊，最多 20 筆），讓其他玩家找到已經開好的局並加入。
/// 沒有資料時是空清單；失敗時是錯誤狀態，畫面用 `ref.invalidate` 重試。
final matchListProvider = FutureProvider.autoDispose<List<GameMatch>>((
  ref,
) async {
  final page = await ref.watch(matchesRepositoryProvider).list();
  return page.items;
}, retry: (_, _) => null);
