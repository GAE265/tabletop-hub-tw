// 店家清單與遊戲搜尋（spec：update-groups-shop-game-pickers 的 groups-calendar-page）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
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

  group('遊戲搜尋', () {
    late FakeGroupsRepository repo;
    late ProviderContainer container;

    GameSearchState state() => container.read(gameSearchProvider);
    GameSearchNotifier search() => container.read(gameSearchProvider.notifier);

    setUp(() {
      repo = FakeGroupsRepository();
      container = makeContainer(repo);
      container.listen(gameSearchProvider, (_, _) {});
    });

    Future<void> wait(int ms) =>
        Future<void>.delayed(Duration(milliseconds: ms));

    test('停止輸入 300 毫秒後才查詢，只查最後一次的關鍵字', () async {
      search().search('阿');
      await wait(100);
      search().search('阿瓦');
      await wait(200);
      expect(repo.gameSearches, isEmpty);
      expect(state().results.isLoading, isTrue);

      await wait(200);
      expect(repo.gameSearches, ['阿瓦']);
      expect(state().results.value!.map((g) => g.name), ['阿瓦隆']);
    });

    test('關鍵字是空白：不查詢，沒有結果', () async {
      search().search('  ');
      await wait(400);
      expect(repo.gameSearches, isEmpty);
      expect(state().results.value, isEmpty);
    });

    test('沒有符合的遊戲：空清單', () async {
      search().search('不存在');
      await wait(400);
      expect(state().results.value, isEmpty);
    });

    test('查詢失敗：保留錯誤', () async {
      repo.gamesError = failure;
      search().search('阿');
      await wait(400);
      expect(state().results.error, isA<ApiException>());
    });

    test('清除：關鍵字與結果都清空，等待中的查詢取消', () async {
      search().search('阿');
      search().clear();
      await wait(400);
      expect(repo.gameSearches, isEmpty);
      expect(state().query, '');
      expect(state().results.value, isEmpty);
    });
  });
}
