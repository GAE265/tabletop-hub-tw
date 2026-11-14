/// `POST /api/v1/groups` 的請求內容。時間一律以 UTC 送出（AGENTS.md 4.3）。
class GroupInput {
  const GroupInput({
    required this.shopId,
    required this.title,
    required this.startAt,
    required this.endAt,
    required this.capacity,
    this.fee,
    this.gameId,
    this.description,
  });

  final String shopId;
  final String title;
  final DateTime startAt;
  final DateTime endAt;
  final int capacity;
  final int? fee;
  final int? gameId;
  final String? description;

  Map<String, dynamic> toJson() => {
    'shop_id': shopId,
    'title': title,
    'start_at': startAt.toUtc().toIso8601String(),
    'end_at': endAt.toUtc().toIso8601String(),
    'capacity': capacity,
    'fee': fee,
    'game_id': gameId,
    'description': description,
  };

  /// `PATCH /api/v1/groups/{id}` 用：店家建立後不能修改，所以不送 shop_id。
  Map<String, dynamic> toUpdateJson() => toJson()..remove('shop_id');
}
