/// 新增店家的回應。對應後端 `POST /api/v1/shops` 的 `ShopCreatedOut`。
class CreatedShop {
  const CreatedShop({
    required this.id,
    required this.name,
    this.phone,
    this.address,
  });

  factory CreatedShop.fromJson(Map<String, dynamic> json) => CreatedShop(
    id: json['id'] as String,
    name: json['name'] as String,
    phone: json['phone'] as String?,
    address: json['address'] as String?,
  );

  final String id;
  final String name;
  final String? phone;
  final String? address;
}

/// 店裡有的一款桌遊。對應 `GET /api/v1/shops/{shop_id}/games` 的 `ShopGameOut`。
class ShopGame {
  const ShopGame({required this.gameId, required this.name});

  factory ShopGame.fromJson(Map<String, dynamic> json) =>
      ShopGame(gameId: json['game_id'] as int, name: json['name'] as String);

  final int gameId;
  final String name;
}

/// 可以加入庫存的桌遊。對應 `GET /api/v1/games` 的 `GameListItem`（只取用得到的欄位）。
class GameChoice {
  const GameChoice({required this.id, required this.name});

  factory GameChoice.fromJson(Map<String, dynamic> json) =>
      GameChoice(id: json['id'] as int, name: json['name'] as String);

  final int id;
  final String name;
}
