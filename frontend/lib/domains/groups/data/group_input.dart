/// `POST /api/v1/groups` 的請求內容。時間一律以 UTC 送出（AGENTS.md 4.3）。
class GroupInput {
  const GroupInput({
    required this.shopId,
    required this.title,
    required this.startAt,
    required this.endAt,
    required this.capacity,
    this.fee,
    this.gameIds = const [],
    this.description,
  });

  final String shopId;
  final String title;
  final DateTime startAt;
  final DateTime endAt;
  final int capacity;
  final int? fee;

  /// 要玩的遊戲，依選擇的順序；空陣列代表不指定遊戲。
  final List<int> gameIds;
  final String? description;

  Map<String, dynamic> toJson() => {
    'shop_id': shopId,
    'title': title,
    'start_at': startAt.toUtc().toIso8601String(),
    'end_at': endAt.toUtc().toIso8601String(),
    'capacity': capacity,
    'fee': fee,
    'game_ids': gameIds,
    'description': description,
  };

  /// `PATCH /api/v1/groups/{id}` 用：店家建立後不能修改，所以不送 shop_id。
  Map<String, dynamic> toUpdateJson() => toJson()..remove('shop_id');
}
