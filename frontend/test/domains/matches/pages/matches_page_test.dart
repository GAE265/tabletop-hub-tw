// 戰績正式頁面：開一局、用編號打開、最近的局（/matches）。
// 操作邏輯已由 state 的測試涵蓋，這裡確認畫面正確呈現 state 並導頁。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/matches/pages/match_detail_page.dart';

import '../../../support/fakes.dart';
import 'support.dart';

const serverError = ApiException(
  code: 'MATCH_GAME_NOT_FOUND',
  message: '找不到這款遊戲',
  statusCode: 404,
);

void main() {
  group('開一局', () {
    testWidgets('選遊戲、日期預設今天、自家，按「開局」後跳到這一局', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      await choose(tester, 'match-game', '阿不思學院');
      await tester.enterText(find.byKey(const Key('match-seat')), '2');
      await tapKey(tester, 'match-create');

      final input = repo.createCalls.single;
      expect(input.gameId, 2);
      expect(input.locationType, 'home');
      expect(input.seatNumber, 2);
      final today = DateTime.now();
      expect(
        (input.playedOn.year, input.playedOn.month, input.playedOn.day),
        (today.year, today.month, today.day),
      );
      expect(find.byType(MatchDetailPage), findsOneWidget);
    });

    testWidgets('沒選遊戲：欄位旁顯示錯誤，不送出', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      await tapKey(tester, 'match-create');
      expect(find.text('請選擇遊戲'), findsOneWidget);
      expect(repo.createCalls, isEmpty);
    });

    testWidgets('選桌遊店：出現店家選單；沒選店家時顯示錯誤；選了就送出店家', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      expect(find.byKey(const Key('match-shop')), findsNothing);
      await choose(tester, 'match-game', '阿瓦隆');
      await tapKey(tester, 'match-location-shop');
      expect(find.byKey(const Key('match-shop')), findsOneWidget);

      await tapKey(tester, 'match-create');
      expect(find.text('請選擇店家'), findsOneWidget);
      expect(repo.createCalls, isEmpty);

      await choose(tester, 'match-shop', '乙店');
      await tapKey(tester, 'match-create');
      expect(repo.createCalls.single.locationType, 'shop');
      expect(repo.createCalls.single.shopId, 's-b');
    });

    testWidgets('店家載入失敗：顯示錯誤與「重試」；重試後出現店家', (tester) async {
      final booking = FakeBookingRepository(
        shopError: const ApiException(code: 'X', message: '店家載入失敗'),
      );
      await pumpMatches(tester, '/matches', booking: booking);
      await tapKey(tester, 'match-location-shop');
      expect(find.textContaining('店家載入失敗'), findsOneWidget);
      booking.shopError = null;
      await tapKey(tester, 'match-shops-retry');
      expect(find.byKey(const Key('match-shop')), findsOneWidget);
    });

    testWidgets('沒有店家：顯示「目前沒有可選的店家」', (tester) async {
      await pumpMatches(
        tester,
        '/matches',
        booking: FakeBookingRepository(shops: const []),
      );
      await tapKey(tester, 'match-location-shop');
      expect(find.text('目前沒有可選的店家'), findsOneWidget);
    });

    testWidgets('遊戲載入失敗：顯示錯誤與「重試」', (tester) async {
      final groups = FakeGroupsRepository()
        ..gamesError = const ApiException(code: 'X', message: '遊戲載入失敗');
      await pumpMatches(tester, '/matches', groups: groups);
      expect(find.textContaining('遊戲載入失敗'), findsOneWidget);
      groups.gamesError = null;
      await tapKey(tester, 'match-games-retry');
      expect(find.byKey(const Key('match-game')), findsOneWidget);
    });

    testWidgets('開局失敗：顯示中文錯誤（不含錯誤代碼），留在原頁', (tester) async {
      final repo = FakeMatchesRepository()..actionError = serverError;
      await pumpMatches(tester, '/matches', repo: repo);
      await choose(tester, 'match-game', '阿瓦隆');
      await tapKey(tester, 'match-create');
      expect(find.text('找不到這款遊戲'), findsOneWidget);
      expect(find.textContaining('MATCH_GAME_NOT_FOUND'), findsNothing);
      expect(find.byType(MatchDetailPage), findsNothing);
    });
  });

  group('從揪團帶入', () {
    final start = DateTime.utc(2026, 11, 21, 8); // 台灣 11/21 16:00

    FakeGroupsRepository groupsWith(List<GameRef> games) =>
        FakeGroupsRepository(
          groups: [
            fakeGroup(
              id: 'g-1',
              title: '週末輕策略',
              startAt: start,
              shopId: 's-b',
              games: games,
            ),
          ],
        );

    testWidgets('上方顯示揪團名稱；店家、桌遊店與唯一的遊戲都已填好；開局帶 group_id', (tester) async {
      final repo = await pumpMatches(
        tester,
        '/matches?group_id=g-1',
        groups: groupsWith(const [GameRef(id: 2, name: '阿不思學院')]),
      );
      expect(inKey('match-group-title', find.text('週末輕策略')), findsOneWidget);
      expect(find.text('阿不思學院'), findsOneWidget);
      expect(find.text('乙店'), findsOneWidget);
      await tapKey(tester, 'match-create');

      final input = repo.createCalls.single;
      expect(input.gameId, 2);
      expect(input.locationType, 'shop');
      expect(input.shopId, 's-b');
      expect(input.groupId, 'g-1');
      expect(find.byType(MatchDetailPage), findsOneWidget);
    });

    testWidgets('揪團有兩款以上遊戲：遊戲留空，要自己選', (tester) async {
      final repo = await pumpMatches(
        tester,
        '/matches?group_id=g-1',
        groups: groupsWith(const [
          GameRef(id: 2, name: '阿不思學院'),
          GameRef(id: 3, name: '馬可波羅'),
        ]),
      );
      await tapKey(tester, 'match-create');
      expect(find.text('請選擇遊戲'), findsOneWidget);
      expect(repo.createCalls, isEmpty);
      expect(find.text('乙店'), findsOneWidget);
    });

    testWidgets('最近的局只列這個揪團的局（帶 group_id 查詢），點進去可以繼續記錄', (tester) async {
      final repo = await pumpMatches(
        tester,
        '/matches?group_id=g-1',
        groups: groupsWith(const []),
      );
      expect(repo.listGroupIds, contains('g-1'));
      expect(repo.listGroupIds, isNot(contains(null)));
      await tapKey(tester, 'match-item-m-1');
      expect(find.byType(MatchDetailPage), findsOneWidget);
    });

    testWidgets('讀取揪團失敗：顯示錯誤與「重試」，不帶 group_id；重試後恢復', (tester) async {
      final groups = groupsWith(
        const [],
      )..error = const ApiException(code: 'NETWORK_ERROR', message: '無法連線到伺服器');
      final repo = await pumpMatches(
        tester,
        '/matches?group_id=g-1',
        groups: groups,
      );
      expect(
        inKey('match-group-error', find.textContaining('揪團載入失敗')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('match-group-title')), findsNothing);

      groups.error = null;
      await tapKey(tester, 'match-group-retry');
      expect(find.byKey(const Key('match-group-error')), findsNothing);
      expect(inKey('match-group-title', find.text('週末輕策略')), findsOneWidget);
      await choose(tester, 'match-game', '阿瓦隆');
      await tapKey(tester, 'match-create');
      expect(repo.createCalls.single.groupId, 'g-1');
    });

    testWidgets('直接打開戰績頁：不顯示揪團名稱、不帶 group_id、最近的局不篩選', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      expect(find.byKey(const Key('match-group-title')), findsNothing);
      expect(repo.listGroupIds, [null]);
      await choose(tester, 'match-game', '阿瓦隆');
      await tapKey(tester, 'match-create');
      expect(repo.createCalls.single.groupId, isNull);
      expect(repo.createCalls.single.locationType, 'home');
    });
  });

  group('最近的局', () {
    testWidgets('列出遊戲、日期、狀態、地點與人數；點一筆打開那一局', (tester) async {
      await pumpMatches(tester, '/matches');
      final item = find.byKey(const Key('match-item-m-1'));
      await tester.ensureVisible(item);
      for (final text in ['血與刃的白薔薇', '進行中']) {
        expect(
          find.descendant(of: item, matching: find.text(text)),
          findsOneWidget,
        );
      }
      expect(
        find.descendant(of: item, matching: find.text('2026/11/20（五）・自家・3 人')),
        findsOneWidget,
      );
      await tapKey(tester, 'match-item-m-1');
      expect(find.byType(MatchDetailPage), findsOneWidget);
    });

    testWidgets('沒有任何一局：「還沒有任何一局，先開一局吧」', (tester) async {
      await pumpMatches(
        tester,
        '/matches',
        repo: FakeMatchesRepository()..listItems = const [],
      );
      expect(find.text('還沒有任何一局，先開一局吧'), findsOneWidget);
    });

    testWidgets('載入失敗：顯示錯誤與「重試」；重試後列出', (tester) async {
      final repo = FakeMatchesRepository()
        ..error = const ApiException(code: 'X', message: '清單載入失敗');
      await pumpMatches(tester, '/matches', repo: repo);
      expect(find.textContaining('清單載入失敗'), findsOneWidget);
      repo.error = null;
      await tapKey(tester, 'match-list-retry');
      expect(find.byKey(const Key('match-item-m-1')), findsOneWidget);
    });

    testWidgets('重新整理：重新查詢清單', (tester) async {
      final repo = FakeMatchesRepository()..listItems = const [];
      await pumpMatches(tester, '/matches', repo: repo);
      expect(find.text('還沒有任何一局，先開一局吧'), findsOneWidget);
      repo.listItems = null;
      await tapKey(tester, 'match-list-refresh');
      expect(find.byKey(const Key('match-item-m-1')), findsOneWidget);
    });
  });

  group('用編號打開', () {
    testWidgets('輸入編號按「打開」：跳到那一局', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      await tester.enterText(find.byKey(const Key('match-open-id')), ' m-1 ');
      await tapKey(tester, 'match-open');
      expect(find.byType(MatchDetailPage), findsOneWidget);
      expect(repo.getCalls.last, 'm-1');
    });

    testWidgets('空白時不動作', (tester) async {
      await pumpMatches(tester, '/matches');
      await tapKey(tester, 'match-open');
      expect(find.byType(MatchDetailPage), findsNothing);
    });
  });

  testWidgets('手機：開局表單與最近的局上下排列', (tester) async {
    await pumpMatches(tester, '/matches', size: const Size(400, 1600));
    final form = tester.getTopLeft(find.byKey(const Key('match-form-card')));
    final list = tester.getTopLeft(find.byKey(const Key('match-list-card')));
    expect(list.dy, greaterThan(form.dy));
    expect(list.dx, form.dx);
  });

  testWidgets('桌機：開局表單與最近的局左右並排', (tester) async {
    await pumpMatches(tester, '/matches', size: const Size(1280, 900));
    final form = tester.getTopLeft(find.byKey(const Key('match-form-card')));
    final list = tester.getTopLeft(find.byKey(const Key('match-list-card')));
    expect(list.dx, greaterThan(form.dx));
    expect(list.dy, form.dy);
  });
}
