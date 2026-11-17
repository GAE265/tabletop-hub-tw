// 店家清單、遊戲清單與篩選（spec：update-groups-shop-game-pickers 的 groups-calendar-page）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/state/group_pickers_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

const failure = ApiException(code: 'NETWORK_ERROR', message: '無法連線');

void main() {
  group('店家清單', () {
    test('載入 GET /api/v1/shops 的店家', () async {
      final container = makeContainer(FakeGroupsRepository());
      final shops = await container.read(shopOptionsProvider.future);
      expect(shops.map((s) => s.name), ['測試桌遊店', '另一間店']);
    });

    test('載入失敗：錯誤；重試後恢復，不自動重試', () async {
      final repo = FakeGroupsRepository()..shopsError = failure;
      final container = makeContainer(repo);
      container.listen(shopOptionsProvider, (_, _) {});
      await expectLater(
        container.read(shopOptionsProvider.future),
        throwsA(isA<ApiException>()),
      );
      expect(repo.shopsCalls, 1);

      repo.shopsError = null;
      container.invalidate(shopOptionsProvider);
      expect(await container.read(shopOptionsProvider.future), hasLength(2));
    });
  });

  group('遊戲清單', () {
    test('載入全部遊戲', () async {
      final repo = FakeGroupsRepository();
      final container = makeContainer(repo);
      final games = await container.read(gameOptionsProvider.future);
      expect(games.map((g) => g.name), ['阿瓦隆', '阿不思學院', '馬可波羅']);
      expect(repo.gamesCalls, 1);
    });

    test('載入失敗：錯誤；重試後恢復，不自動重試', () async {
      final repo = FakeGroupsRepository()..gamesError = failure;
      final container = makeContainer(repo);
      container.listen(gameOptionsProvider, (_, _) {});
      await expectLater(
        container.read(gameOptionsProvider.future),
        throwsA(isA<ApiException>()),
      );
      expect(repo.gamesCalls, 1);

      repo.gamesError = null;
      container.invalidate(gameOptionsProvider);
      expect(await container.read(gameOptionsProvider.future), hasLength(3));
    });
  });

  group('在本機篩選遊戲', () {
    const games = [
      GameRef(id: 1, name: '阿瓦隆'),
      GameRef(id: 2, name: '阿不思學院'),
      GameRef(id: 3, name: 'Catan 卡坦島'),
    ];

    test('關鍵字是空白：全部列出', () {
      expect(filterGames(games, '  '), games);
    });

    test('名稱部分相符', () {
      expect(filterGames(games, '阿').map((g) => g.id), [1, 2]);
    });

    test('英文不分大小寫、去掉前後空白', () {
      expect(filterGames(games, ' catan ').map((g) => g.id), [3]);
    });

    test('沒有符合：空清單', () {
      expect(filterGames(games, '不存在'), isEmpty);
    });
  });
}
