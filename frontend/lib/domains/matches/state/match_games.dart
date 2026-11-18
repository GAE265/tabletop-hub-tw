import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../groups/data/group.dart';
import '../../groups/data/groups_repository.dart';

/// 開局時的遊戲選項，取自 `GET /api/v1/games`（`core/games`，立倫）。
///
/// 比照 `matchShopsProvider` 借用其他 domain 的 repository：遊戲清單目前由
/// groups 的 `listGames()` 呼叫（依名稱排序、超過一頁自動補齊）。失敗不自動重試，
/// 交給畫面上的「重試」（`ref.invalidate`）。
final matchGameOptionsProvider = FutureProvider.autoDispose<List<GameRef>>(
  (ref) => ref.watch(groupsRepositoryProvider).listGames(),
  retry: (_, _) => null,
);
