// 戰績正式頁面：一局（/matches/:id）。
// 操作邏輯已由 state 的測試涵蓋，這裡確認畫面正確呈現 state、權限與覆蓋提示。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/pages/matches_page.dart';

import '../../../support/fakes.dart';
import 'support.dart';

const detail = '/matches/m-1';

void main() {
  testWidgets('載入中：顯示「載入中…」', (tester) async {
    final repo = FakeMatchesRepository();
    await pumpMatches(tester, detail, repo: repo, settle: false);
    expect(find.text('載入中…'), findsOneWidget);
    await tester.pumpAndSettle();
  });

  testWidgets('載入失敗：顯示中文錯誤與「重試」；重試後顯示這一局', (tester) async {
    final repo = FakeMatchesRepository()
      ..error = const ApiException(
        code: 'MATCH_NOT_FOUND',
        message: '找不到這一局',
        statusCode: 404,
      );
    await pumpMatches(tester, detail, repo: repo);
    expect(find.textContaining('找不到這一局'), findsOneWidget);
    expect(find.textContaining('MATCH_NOT_FOUND'), findsNothing);
    repo.error = null;
    await tapKey(tester, 'match-retry');
    expect(find.text('血與刃的白薔薇'), findsOneWidget);
  });

  testWidgets('一局的資料：遊戲、日期、狀態、地點、開局者、結果、人數與有效紀錄', (tester) async {
    await pumpMatches(tester, detail);
    final card = find.byKey(const Key('match-info'));
    for (final text in [
      '血與刃的白薔薇',
      '進行中',
      '自家',
      '2026/11/20（五）',
      '開局者：測試玩家',
      '結果：尚未記錄',
    ]) {
      expect(
        find.descendant(of: card, matching: find.text(text)),
        findsOneWidget,
        reason: text,
      );
    }
    expect(find.text('3 人參加、2 人有帳號、0 人已確認'), findsOneWidget);
    expect(find.text('尚未成為有效紀錄'), findsOneWidget);
  });

  testWidgets('參加者：座位、名字、有沒有帳號；自己標示「（我）」', (tester) async {
    await pumpMatches(tester, detail);
    expect(inKey('participant-p-1', find.text('測試玩家（我）')), findsOneWidget);
    expect(inKey('participant-p-3', find.text('Amy')), findsOneWidget);
    expect(
      inKey('participant-p-3', find.textContaining('沒有帳號')),
      findsOneWidget,
    );
    expect(
      inKey('participant-p-2', find.textContaining('尚未確認')),
      findsOneWidget,
    );
  });

  testWidgets('返回：回到戰績頁', (tester) async {
    await pumpMatches(tester, detail);
    await tapKey(tester, 'match-back');
    expect(find.byType(MatchesPage), findsOneWidget);
  });

  testWidgets('重新整理：再查詢一次這一局', (tester) async {
    final repo = await pumpMatches(tester, detail);
    final before = repo.getCalls.length;
    await tapKey(tester, 'match-refresh');
    expect(repo.getCalls.length, before + 1);
  });

  group('不是參加者', () {
    testWidgets('只看到資料與「加入這一局」，沒有回合與結果表單、沒有移除', (tester) async {
      await pumpMatches(tester, detail, userId: 'u-other');
      expect(find.byKey(const Key('join')), findsOneWidget);
      expect(find.byKey(const Key('turn-form')), findsNothing);
      expect(find.byKey(const Key('result-form')), findsNothing);
      expect(find.byKey(const Key('result-readonly')), findsOneWidget);
      expect(find.byKey(const Key('remove-p-1')), findsNothing);
      expect(find.byKey(const Key('add-named')), findsNothing);
    });

    testWidgets('加入：座位選填，送出後顯示「已加入這一局」', (tester) async {
      final repo = FakeMatchesRepository(currentUserId: 'u-other');
      await pumpMatches(tester, detail, repo: repo, userId: 'u-other');
      await tester.enterText(find.byKey(const Key('join-seat')), '4');
      await tapKey(tester, 'join');
      expect(repo.addCalls.single.seatNumber, 4);
      expect(repo.addCalls.single.displayName, isNull);
      expect(find.text('已加入這一局'), findsOneWidget);
    });
  });

  group('參加者的操作', () {
    testWidgets('新增沒有帳號的人：成功後清空欄位', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tester.enterText(find.byKey(const Key('add-named-name')), 'Bob');
      await tester.enterText(find.byKey(const Key('add-named-seat')), '5');
      await tapKey(tester, 'add-named');
      expect(repo.addCalls.single.displayName, 'Bob');
      expect(repo.addCalls.single.seatNumber, 5);
      expect(find.text('已新增 Bob'), findsOneWidget);
      final name = tester.widget<TextField>(
        find.byKey(const Key('add-named-name')),
      );
      expect(name.controller!.text, isEmpty);
    });

    testWidgets('名字空白：顯示「請輸入名字」，不送出', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tapKey(tester, 'add-named');
      expect(find.text('請輸入名字'), findsOneWidget);
      expect(repo.addCalls, isEmpty);
    });

    testWidgets('移除：先跳確認；按「取消」不送出，按「移除」才送出', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tapKey(tester, 'remove-p-3');
      expect(find.textContaining('座位 3「Amy」'), findsOneWidget);
      await tapKey(tester, 'remove-cancel');
      expect(repo.removeCalls, isEmpty);

      await tapKey(tester, 'remove-p-3');
      await tapKey(tester, 'remove-confirm');
      expect(repo.removeCalls, ['p-3']);
      expect(find.byKey(const Key('participant-p-3')), findsNothing);
    });

    testWidgets('座位已出現在回合：顯示訊息與相關回合', (tester) async {
      final repo = FakeMatchesRepository(
        match: fakeMatch(
          turns: [fakeMatchTurn(turnNumber: 1), fakeMatchTurn(turnNumber: 2)],
        ),
      );
      await pumpMatches(tester, detail, repo: repo);
      await tapKey(tester, 'remove-p-2');
      await tapKey(tester, 'remove-confirm');
      final error = find.byKey(const Key('match-error'));
      expect(
        find.descendant(of: error, matching: find.textContaining('相關回合：1、2')),
        findsOneWidget,
      );
      expect(find.textContaining('MATCH_PARTICIPANT_HAS_TURNS'), findsNothing);
      expect(find.byKey(const Key('participant-p-2')), findsOneWidget);
    });

    testWidgets('操作進行中：按鈕停用並顯示進度條', (tester) async {
      final repo = FakeMatchesRepository()..actionGate = Completer<void>();
      await pumpMatches(tester, detail, repo: repo);
      await tester.enterText(find.byKey(const Key('add-named-name')), 'Bob');
      await tester.ensureVisible(find.byKey(const Key('add-named')));
      await tester.tap(find.byKey(const Key('add-named')));
      await tester.pump();
      expect(find.byKey(const Key('match-busy')), findsOneWidget);
      final button = tester.widget<ButtonStyleButton>(
        find.byKey(const Key('add-named')),
      );
      expect(button.onPressed, isNull);
      repo.actionGate!.complete();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('match-busy')), findsNothing);
    });
  });

  group('回合', () {
    testWidgets('沒有回合紀錄：顯示提示', (tester) async {
      await pumpMatches(tester, detail);
      expect(find.text('還沒有回合紀錄（回合紀錄是選填的，只記結果也可以）'), findsOneWidget);
    });

    testWidgets('回合清單：第幾回合、首家座位、出牌座位與數量', (tester) async {
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(turns: [fakeMatchTurn(turnNumber: 1)]),
        ),
      );
      expect(inKey('turn-1', find.text('第 1 回合・首家座位 1')), findsOneWidget);
      expect(inKey('turn-1', find.textContaining('出牌座位 1、2')), findsOneWidget);
    });

    testWidgets('回合沒有首家：標題只有第幾回合', (tester) async {
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(
            turns: [fakeMatchTurn(turnNumber: 2, seatNumber: null)],
          ),
        ),
      );
      expect(inKey('turn-2', find.text('第 2 回合')), findsOneWidget);
      expect(inKey('turn-2', find.textContaining('首家')), findsNothing);
    });

    testWidgets('回合表單：標籤是「首家（有金幣，選填）」，畫面不再出現「主導」', (tester) async {
      await pumpMatches(tester, detail);
      await tester.ensureVisible(find.byKey(const Key('turn-first-seat')));
      expect(find.text('首家（有金幣，選填）'), findsOneWidget);
      expect(find.text('本回合首家（選填）'), findsNothing);
      expect(find.textContaining('主導'), findsNothing);
    });

    testWidgets('沒選首家只選出牌座位：可以送出，seat_number 為 null', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tapKey(tester, 'turn-seat-1');
      await tapKey(tester, 'turn-submit');
      expect(find.text('請選擇主導的座位'), findsNothing);
      expect(repo.turnCalls.single.input.seatNumber, isNull);
      expect(find.byKey(const Key('turn-1')), findsOneWidget);
      expect(inKey('turn-1', find.text('第 1 回合')), findsOneWidget);
    });

    testWidgets('記錄回合：選首家、出牌座位與數量後送出，清單多一筆', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await choose(tester, 'turn-first-seat', '座位 2・玩家乙');
      await tapKey(tester, 'turn-seat-1');
      await tapKey(tester, 'turn-seat-2');
      await tapKey(tester, 'turn-doubleBlade-inc');
      await tapKey(tester, 'turn-white-rose');
      await tapKey(tester, 'turn-cardinal');
      await tapKey(tester, 'turn-submit');

      final call = repo.turnCalls.single;
      expect(call.overwrite, isFalse);
      expect(call.input.turnNumber, 1);
      expect(call.input.seatNumber, 2);
      final data = call.input.gameData;
      expect(data['played_seat_numbers'], [1, 2]);
      expect(data['double_blade_count'], 1);
      expect(data['has_white_rose'], isTrue);
      expect(data['has_cardinal'], isTrue);
      expect(find.byKey(const Key('turn-1')), findsOneWidget);
    });

    testWidgets('整桌都不出牌：不選出牌座位也能送出，沒有欄位錯誤', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tapKey(tester, 'turn-submit');
      expect(find.text('請至少選一個出牌的座位'), findsNothing);
      expect(
        repo.turnCalls.single.input.gameData['played_seat_numbers'],
        isEmpty,
      );
      expect(find.byKey(const Key('turn-1')), findsOneWidget);
    });

    testWidgets('回合表單有「司教」開關', (tester) async {
      await pumpMatches(tester, detail);
      await tester.ensureVisible(find.byKey(const Key('turn-cardinal')));
      expect(
        find.descendant(
          of: find.byKey(const Key('turn-cardinal')),
          matching: find.text('司教'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('同一回合已有人記錄：顯示覆蓋提示；「取消」只關提示，「更新」帶 overwrite 重送', (tester) async {
      final repo = FakeMatchesRepository(
        match: fakeMatch(turns: [fakeMatchTurn(turnNumber: 1)]),
      );
      await pumpMatches(tester, detail, repo: repo);
      // 別人已經記了第 1 回合，我這邊的表單還停在第 1 回合（模擬兩個人同時記錄）
      await tester.enterText(find.byKey(const Key('turn-number')), '1');
      await choose(tester, 'turn-first-seat', '座位 1・測試玩家');
      await tapKey(tester, 'turn-seat-1');
      await tapKey(tester, 'turn-submit');

      final prompt = find.byKey(const Key('turn-overwrite'));
      expect(prompt, findsOneWidget);
      expect(
        find.descendant(of: prompt, matching: find.text('已經有人記錄了，要更新嗎？')),
        findsOneWidget,
      );
      await tapKey(tester, 'turn-overwrite-cancel');
      expect(prompt, findsNothing);
      expect(repo.turnCalls, hasLength(1));

      await tapKey(tester, 'turn-submit');
      await tapKey(tester, 'turn-overwrite-confirm');
      expect(repo.turnCalls.last.overwrite, isTrue);
      expect(prompt, findsNothing);
    });
  });

  group('結果與確認', () {
    testWidgets('記錄結果：選獲勝陣營與每個座位的陣營後送出，顯示結果', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await choose(tester, 'result-winning', '薔薇陣營');
      await choose(tester, 'result-faction-1', '薔薇陣營');
      await choose(tester, 'result-faction-2', '血刃陣營');
      await choose(tester, 'result-faction-3', '薔薇陣營');
      await tapKey(tester, 'result-submit');

      final call = repo.resultCalls.single;
      expect(call.input.winningFaction, 'rose');
      expect(call.input.factions, {1: 'rose', 2: 'blood_blade', 3: 'rose'});
      // 結果表單在頁面下方，捲回最上面看這一局的資料
      await tester.scrollUntilVisible(
        find.byKey(const Key('match-info')),
        -300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(inKey('match-info', find.text('結果：薔薇陣營獲勝')), findsOneWidget);
      expect(inKey('match-info', find.text('已結束')), findsOneWidget);
    });

    testWidgets('沒選完：顯示欄位錯誤，不送出', (tester) async {
      final repo = await pumpMatches(tester, detail);
      await tapKey(tester, 'result-submit');
      expect(find.text('請選擇獲勝陣營'), findsOneWidget);
      expect(find.textContaining('請為每個座位選擇陣營'), findsOneWidget);
      expect(repo.resultCalls, isEmpty);
    });

    testWidgets('已有結果：顯示覆蓋提示與既有結果；「更新」帶 overwrite 重送', (tester) async {
      final repo = FakeMatchesRepository(
        match: fakeMatch(
          status: 'finished',
          result: const {'type': 'faction', 'winning_faction': 'blood_blade'},
        ),
      );
      await pumpMatches(tester, detail, repo: repo);
      await choose(tester, 'result-winning', '薔薇陣營');
      for (final seat in [1, 2, 3]) {
        await choose(tester, 'result-faction-$seat', '薔薇陣營');
      }
      await tapKey(tester, 'result-submit');

      final prompt = find.byKey(const Key('result-overwrite'));
      expect(
        find.descendant(of: prompt, matching: find.textContaining('血刃陣營獲勝')),
        findsOneWidget,
      );
      await tapKey(tester, 'result-overwrite-confirm');
      expect(repo.resultCalls.last.overwrite, isTrue);
    });

    testWidgets('已結束、我還沒確認：按「確認這局的紀錄」後按鈕消失', (tester) async {
      final repo = FakeMatchesRepository(
        match: fakeMatch(
          status: 'finished',
          result: const {'type': 'faction', 'winning_faction': 'rose'},
        ),
      );
      await pumpMatches(tester, detail, repo: repo);
      expect(find.byKey(const Key('join')), findsNothing);
      expect(find.byKey(const Key('remove-p-1')), findsNothing);
      await tapKey(tester, 'confirm');
      expect(repo.confirmCalls, ['p-1']);
      expect(find.byKey(const Key('confirm')), findsNothing);
      expect(find.text('已確認'), findsWidgets);
    });
  });
}
