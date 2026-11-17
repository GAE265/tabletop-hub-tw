/// 店家 DTO。對應後端 `GET /api/v1/shops` 的 `ShopOut`。
class Shop {
  const Shop({required this.id, required this.name});

  factory Shop.fromJson(Map<String, dynamic> json) =>
      Shop(id: json['id'] as String, name: json['name'] as String);

  final String id;
  final String name;
}

class ShopPage {
  const ShopPage({required this.items, required this.total});

  factory ShopPage.fromJson(Map<String, dynamic> json) => ShopPage(
    items: [
      for (final i in json['items'] as List)
        Shop.fromJson(i as Map<String, dynamic>),
    ],
    total: json['total'] as int,
  );

  final List<Shop> items;
  final int total;
}
