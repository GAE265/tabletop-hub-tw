import '../data/group.dart';
import 'group_clock.dart';

/// 開團主或成員替揪團填入戰績：產生帶好揪團資料的戰績頁網址（`/matches?...`）。
///
/// - 遊戲帶揪團的第一款；揪團沒選遊戲時不帶，由使用者在戰績頁選。
/// - 日期用揪團開始時間的牆上日期（與揪團頁顯示的一致）。
/// - 地點是桌遊店，帶揪團的店家；帶 `group_id`，開局後這一局會連到這個揪團。
Uri groupMatchLink(GroupClock clock, Group group) {
  final start = clock.toLocal(group.startAt);
  return Uri(
    path: '/matches',
    queryParameters: {
      if (group.games.isNotEmpty) 'game_id': '${group.games.first.id}',
      'date': '${start.year}-${_two(start.month)}-${_two(start.day)}',
      'shop_id': group.shop.id,
      'group_id': group.id,
    },
  );
}

String _two(int n) => n.toString().padLeft(2, '0');
