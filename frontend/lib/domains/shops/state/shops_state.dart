import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/dev/data/dev_user.dart';
import '../data/shop_models.dart';
import '../data/shops_repository.dart';

/// 新增店家與庫存管理畫面的狀態。[message] 顯示最近一次操作的結果或錯誤。
class ShopsState {
  const ShopsState({
    this.loading = false,
    this.message,
    this.isError = false,
    this.createdShop,
    this.inventory = const [],
    this.inventoryLoaded = false,
    this.choices = const [],
  });

  final bool loading;
  final String? message;
  final bool isError;

  /// 這次新增成功的店家；畫面看到它就前往這間店的庫存頁。
  final CreatedShop? createdShop;
  final List<ShopGame> inventory;

  /// 庫存至少載入成功過一次；用來分辨「還沒載入」與「載入了但沒有資料」。
  final bool inventoryLoaded;
  final List<GameChoice> choices;

  ShopsState copyWith({
    bool? loading,
    String? message,
    bool? isError,
    CreatedShop? createdShop,
    List<ShopGame>? inventory,
    bool? inventoryLoaded,
    List<GameChoice>? choices,
  }) => ShopsState(
    loading: loading ?? this.loading,
    message: message ?? this.message,
    isError: isError ?? this.isError,
    createdShop: createdShop ?? this.createdShop,
    inventory: inventory ?? this.inventory,
    inventoryLoaded: inventoryLoaded ?? this.inventoryLoaded,
    choices: choices ?? this.choices,
  );
}

class ShopsNotifier extends Notifier<ShopsState> {
  ShopsRepository get _repo => ref.read(shopsRepositoryProvider);

  @override
  ShopsState build() => const ShopsState();

  /// 執行一個操作：顯示載入中，成功時用 [action] 回傳的函式更新狀態，失敗時顯示錯誤。
  Future<void> _run(
    Future<ShopsState Function(ShopsState)> Function() action,
  ) async {
    state = state.copyWith(loading: true);
    try {
      final apply = await action();
      state = apply(state).copyWith(loading: false, isError: false);
    } on ApiException catch (e) {
      state = state.copyWith(
        loading: false,
        isError: true,
        message: '${e.code}：${e.message}',
      );
    }
  }

  /// 新增店家。電話、地址去掉前後空白，留空就不送。
  Future<void> createShop({
    required String name,
    String? phone,
    String? address,
  }) async {
    final trimmedName = name.trim();
    if (trimmedName.isEmpty) {
      state = state.copyWith(isError: true, message: '請輸入店名');
      return;
    }
    await _run(() async {
      final shop = await _repo.createShop(
        name: trimmedName,
        phone: _blankToNull(phone),
        address: _blankToNull(address),
      );
      return (ShopsState s) =>
          s.copyWith(createdShop: shop, message: '已新增店家「${shop.name}」');
    });
  }

  Future<void> loadInventory(String shopId) => _run(() async {
    final items = await _repo.listGames(shopId);
    return (ShopsState s) => s.copyWith(
      inventory: items,
      inventoryLoaded: true,
      message: '庫存共 ${items.length} 款',
    );
  });

  Future<void> loadChoices() => _run(() async {
    final choices = await _repo.listGameChoices();
    return (ShopsState s) => s.copyWith(choices: choices);
  });

  Future<void> addGame(String shopId, int gameId) => _run(() async {
    await _repo.addGame(shopId, gameId);
    final items = await _repo.listGames(shopId);
    return (ShopsState s) =>
        s.copyWith(inventory: items, inventoryLoaded: true, message: '已加入庫存');
  });

  Future<void> removeGame(String shopId, int gameId) => _run(() async {
    await _repo.removeGame(shopId, gameId);
    final items = await _repo.listGames(shopId);
    return (ShopsState s) =>
        s.copyWith(inventory: items, inventoryLoaded: true, message: '已移除');
  });
}

String? _blankToNull(String? value) {
  final trimmed = value?.trim();
  return (trimmed == null || trimmed.isEmpty) ? null : trimmed;
}

final shopsProvider = NotifierProvider<ShopsNotifier, ShopsState>(
  ShopsNotifier.new,
);

/// 導覽列的「店家」要前往的路徑。
///
/// 剛新增完店家時去新店的庫存（身分裡的店家還是舊的，要以 [createdShopId] 為準）；
/// 店員已經有店就去自己店的庫存；其他情況（沒有店的店員、管理員）去新增店家。
String resolveShopsEntryPath(DevUser? user, String? createdShopId) {
  if (createdShopId != null) return '/shops/$createdShopId/games';
  final shopId = user?.shopId;
  if (user?.role == 'shop_staff' && shopId != null) {
    return '/shops/$shopId/games';
  }
  return '/shops/new';
}
