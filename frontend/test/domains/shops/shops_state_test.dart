import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/domains/shops/data/shop_models.dart';
import 'package:tabletop_hub/domains/shops/data/shops_repository.dart';
import 'package:tabletop_hub/domains/shops/state/shops_state.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer(FakeShopsRepository repo) {
  final container = ProviderContainer(
    overrides: [shopsRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}

const conflict = ApiException(
  code: 'SHOP_STAFF_ALREADY_HAS_SHOP',
  message: '這個店家帳號已經有所屬店家，不能再新增',
  statusCode: 409,
);

const staffWithoutShop = DevUser(
  id: 'u-new-staff',
  displayName: '新店員',
  role: 'shop_staff',
);

void main() {
  group('新增店家', () {
    test('成功：記下新店，沒有錯誤', () async {
      final repo = FakeShopsRepository();
      final container = makeContainer(repo);
      await container
          .read(shopsProvider.notifier)
          .createShop(name: '新桌遊店', phone: '0912345678', address: '台北');
      final state = container.read(shopsProvider);
      expect(state.createdShop?.id, 's-new');
      expect(state.createdShop?.name, '新桌遊店');
      expect(state.isError, isFalse);
      expect(repo.createCalls.single.phone, '0912345678');
    });

    test('電話與地址留空：送出時不帶這兩個欄位', () async {
      final repo = FakeShopsRepository();
      final container = makeContainer(repo);
      await container
          .read(shopsProvider.notifier)
          .createShop(name: '新桌遊店', phone: '  ', address: '');
      expect(repo.createCalls.single.phone, isNull);
      expect(repo.createCalls.single.address, isNull);
    });

    test('店名空白：不呼叫後端，顯示錯誤', () async {
      final repo = FakeShopsRepository();
      final container = makeContainer(repo);
      await container.read(shopsProvider.notifier).createShop(name: '   ');
      final state = container.read(shopsProvider);
      expect(repo.createCalls, isEmpty);
      expect(state.isError, isTrue);
      expect(state.createdShop, isNull);
    });

    test('後端回 409：顯示錯誤代碼與訊息，不記新店', () async {
      final container = makeContainer(FakeShopsRepository(error: conflict));
      await container.read(shopsProvider.notifier).createShop(name: '第二間');
      final state = container.read(shopsProvider);
      expect(state.isError, isTrue);
      expect(state.message, contains('SHOP_STAFF_ALREADY_HAS_SHOP'));
      expect(state.createdShop, isNull);
      expect(state.loading, isFalse);
    });
  });

  group('庫存', () {
    test('載入中：等後端回應時 loading 為 true，回來後為 false', () async {
      final repo = FakeShopsRepository()..gate = Completer<void>();
      final container = makeContainer(repo);
      final pending = container
          .read(shopsProvider.notifier)
          .loadInventory('s-1');
      expect(container.read(shopsProvider).loading, isTrue);
      repo.gate!.complete();
      await pending;
      expect(container.read(shopsProvider).loading, isFalse);
    });

    test('有資料：列出庫存', () async {
      final repo = FakeShopsRepository(
        inventory: const [ShopGame(gameId: 1, name: '卡坦島')],
      );
      final container = makeContainer(repo);
      await container.read(shopsProvider.notifier).loadInventory('s-1');
      final state = container.read(shopsProvider);
      expect(state.inventory.map((g) => g.name), ['卡坦島']);
      expect(state.inventoryLoaded, isTrue);
    });

    test('沒有資料：庫存為空但已載入', () async {
      final container = makeContainer(FakeShopsRepository());
      await container.read(shopsProvider.notifier).loadInventory('s-1');
      final state = container.read(shopsProvider);
      expect(state.inventory, isEmpty);
      expect(state.inventoryLoaded, isTrue);
      expect(state.isError, isFalse);
    });

    test('錯誤：顯示錯誤訊息，恢復後重新載入成功', () async {
      final repo = FakeShopsRepository(
        error: const ApiException(code: 'NETWORK_ERROR', message: '無法連線'),
      );
      final container = makeContainer(repo);
      await container.read(shopsProvider.notifier).loadInventory('s-1');
      expect(container.read(shopsProvider).isError, isTrue);
      expect(container.read(shopsProvider).inventoryLoaded, isFalse);

      repo.error = null;
      await container.read(shopsProvider.notifier).loadInventory('s-1');
      expect(container.read(shopsProvider).isError, isFalse);
      expect(container.read(shopsProvider).inventoryLoaded, isTrue);
    });

    test('載入可加入的桌遊清單', () async {
      final container = makeContainer(FakeShopsRepository());
      await container.read(shopsProvider.notifier).loadChoices();
      expect(container.read(shopsProvider).choices.map((c) => c.name), [
        '卡坦島',
        '狼人殺',
      ]);
    });

    test('加入後列表更新', () async {
      final container = makeContainer(FakeShopsRepository());
      final notifier = container.read(shopsProvider.notifier);
      await notifier.loadChoices();
      await notifier.addGame('s-1', 2);
      expect(container.read(shopsProvider).inventory.map((g) => g.name), [
        '狼人殺',
      ]);
      expect(container.read(shopsProvider).isError, isFalse);
    });

    test('加入失敗（已經有這款）：顯示錯誤，列表不變', () async {
      final repo = FakeShopsRepository(
        inventory: const [ShopGame(gameId: 1, name: '卡坦島')],
      );
      final container = makeContainer(repo);
      final notifier = container.read(shopsProvider.notifier);
      await notifier.loadInventory('s-1');
      repo.error = const ApiException(
        code: 'SHOP_GAME_ALREADY_EXISTS',
        message: '這間店已經有這款桌遊',
        statusCode: 409,
      );
      await notifier.addGame('s-1', 1);
      final state = container.read(shopsProvider);
      expect(state.isError, isTrue);
      expect(state.message, contains('SHOP_GAME_ALREADY_EXISTS'));
      expect(state.inventory.map((g) => g.name), ['卡坦島']);
    });

    test('移除後列表更新', () async {
      final repo = FakeShopsRepository(
        inventory: const [
          ShopGame(gameId: 1, name: '卡坦島'),
          ShopGame(gameId: 2, name: '狼人殺'),
        ],
      );
      final container = makeContainer(repo);
      final notifier = container.read(shopsProvider.notifier);
      await notifier.loadInventory('s-1');
      await notifier.removeGame('s-1', 1);
      expect(container.read(shopsProvider).inventory.map((g) => g.name), [
        '狼人殺',
      ]);
    });
  });

  group('店家入口（導覽列的「店家」要去哪）', () {
    test('店員有店：直接去自己店的庫存', () {
      expect(resolveShopsEntryPath(fakeStaff, null), '/shops/s-shop/games');
    });

    test('店員沒有店：去新增店家', () {
      expect(resolveShopsEntryPath(staffWithoutShop, null), '/shops/new');
    });

    test('剛新增完店家：去新店的庫存（身分裡的店家還是舊的）', () {
      expect(
        resolveShopsEntryPath(staffWithoutShop, 's-new'),
        '/shops/s-new/games',
      );
    });

    test('管理員：去新增店家', () {
      expect(resolveShopsEntryPath(fakeAdmin, null), '/shops/new');
    });
  });
}
