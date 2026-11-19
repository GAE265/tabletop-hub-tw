import '../data/group.dart';

/// 開團主或成員替揪團填入戰績：產生戰績頁網址 `/matches?group_id=<揪團 id>`。
///
/// 只帶揪團 id；揪團名稱、店家與遊戲由戰績頁讀取揪團後自行帶入。
Uri groupMatchLink(Group group) =>
    Uri(path: '/matches', queryParameters: {'group_id': group.id});
