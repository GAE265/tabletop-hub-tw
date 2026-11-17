// 正式開團／編輯表單（spec：groups-calendar-page 的「開團與編輯表單」；店家與遊戲的
// 下拉選單見 update-groups-shop-game-pickers）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/pages/group_form_page.dart';
import 'package:tabletop_hub/domains/groups/state/group_form_state.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

final day = DateTime(2026, 11, 20);

GroupFormData valid({Duration end = const Duration(hours: 21)}) =>
    GroupFormData(
      shopId: 's-shop',
      title: '新手教學團',
      date: day,
      startTime: const Duration(hours: 19),
      endTime: end,
      capacity: '4',
    );

/// 從一個首頁 push 表單，才能確認送出成功後有關閉表單。
Widget launcher(GroupFormData initial, {String? groupId}) => Builder(
  builder: (context) => Scaffold(
    body: TextButton(
      onPressed: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupFormPage(initial: initial, groupId: groupId),
        ),
      ),
      child: const Text('open'),
    ),
  ),
);

Future<void> openForm(
  WidgetTester tester,
  FakeGroupsRepository repo,
  GroupFormData initial, {
  String? groupId,
}) async {
  await pumpGroupsWidget(
    tester,
    launcher(initial, groupId: groupId),
    repo: repo,
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

Future<void> submit(WidgetTester tester, String label) async {
  await tester.ensureVisible(find.text(label));
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('開團成功：呼叫 API 並關閉表單', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, valid());
    expect(find.byKey(const Key('group-form-page')), findsOneWidget);
    expect(find.text('2026/11/20'), findsOneWidget);

    await submit(tester, '送出');
    expect(repo.createCalls.single.title, '新手教學團');
    expect(find.byKey(const Key('group-form-page')), findsNothing);
  });

  testWidgets('缺少標題：顯示「請填寫標題」，不呼叫 API', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, GroupFormData(date: day));
    await submit(tester, '送出');
    expect(find.text('請填寫標題'), findsOneWidget);
    expect(repo.createCalls, isEmpty);
  });

  testWidgets('結束時間早於開始時間：顯示錯誤，不呼叫 API', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, valid(end: const Duration(hours: 18)));
    await submit(tester, '送出');
    expect(find.text('結束時間要晚於開始時間'), findsOneWidget);
    expect(repo.createCalls, isEmpty);
  });

  testWidgets('後端驗證失敗：保留輸入內容，顯示後端訊息', (tester) async {
    final repo = FakeGroupsRepository()
      ..actionError = const ApiException(
        code: 'SHOP_NOT_FOUND',
        message: '找不到這間店家',
        statusCode: 404,
      );
    await openForm(tester, repo, valid());
    await submit(tester, '送出');
    expect(find.text('找不到這間店家'), findsOneWidget);
    expect(find.text('新手教學團'), findsOneWidget);
    expect(find.byKey(const Key('group-form-page')), findsOneWidget);
  });

  testWidgets('編輯：帶入現有值，按「儲存」', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 20, 19))],
    );
    await openForm(
      tester,
      repo,
      valid().copyWith(title: '週末輕策略'),
      groupId: 'g-1',
    );
    expect(find.text('週末輕策略'), findsOneWidget);
    await submit(tester, '儲存');
    expect(repo.updateCalls.single.$1, 'g-1');
  });

  group('店家下拉選單', () {
    testWidgets('列出店家，選擇後以該店家開團', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid().copyWith(shopId: ''));
      await tester.tap(find.byKey(const Key('group-shop-field')));
      await tester.pumpAndSettle();
      expect(find.text('測試桌遊店'), findsWidgets);
      await tester.tap(find.text('另一間店').last);
      await tester.pumpAndSettle();
      await submit(tester, '送出');
      expect(repo.createCalls.single.shopId, 's-other');
    });

    testWidgets('沒選店家：顯示「請選擇店家」，不呼叫 API', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid().copyWith(shopId: ''));
      await submit(tester, '送出');
      expect(find.text('請選擇店家'), findsOneWidget);
      expect(repo.createCalls, isEmpty);
    });

    testWidgets('店家清單載入失敗：顯示錯誤與「重試」', (tester) async {
      final repo = FakeGroupsRepository()
        ..shopsError = const ApiException(
          code: 'NETWORK_ERROR',
          message: '無法連線',
        );
      await openForm(tester, repo, valid());
      expect(find.text('無法連線'), findsOneWidget);
      repo.shopsError = null;
      await tester.tap(find.text('重試'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group-shop-field')), findsOneWidget);
    });

    testWidgets('沒有手動輸入店家 ID 與遊戲 ID 的欄位', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(find.textContaining('店家 ID'), findsNothing);
      expect(find.textContaining('遊戲 ID'), findsNothing);
    });
  });

  group('遊戲搜尋與複選', () {
    final search = find.byKey(const Key('game-search-input'));

    Future<void> type(WidgetTester tester, String text) async {
      await tester.ensureVisible(search);
      await tester.enterText(search, text);
      // 停止輸入 300 毫秒後才查詢
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
    }

    Future<void> pick(WidgetTester tester, int id) async {
      final option = find.byKey(Key('game-option-$id'));
      await tester.ensureVisible(option);
      await tester.tap(option);
      await tester.pumpAndSettle();
    }

    testWidgets('搜尋並選兩款：依選擇順序顯示標籤，送出 game_ids', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      await type(tester, '馬');
      await pick(tester, 3);
      expect(find.byKey(const Key('game-chip-3')), findsOneWidget);
      expect(tester.widget<TextField>(search).controller!.text, isEmpty);

      await type(tester, '阿瓦');
      await pick(tester, 1);
      expect(
        tester.getTopLeft(find.byKey(const Key('game-chip-3'))).dx,
        lessThan(tester.getTopLeft(find.byKey(const Key('game-chip-1'))).dx),
      );
      await submit(tester, '送出');
      expect(repo.createCalls.single.gameIds, [3, 1]);
    });

    testWidgets('已選的遊戲不再出現在搜尋結果中', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      await type(tester, '阿');
      await pick(tester, 1);
      await type(tester, '阿');
      expect(find.byKey(const Key('game-option-1')), findsNothing);
      expect(find.byKey(const Key('game-option-2')), findsOneWidget);
    });

    testWidgets('移除已選的遊戲', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      await type(tester, '阿瓦');
      await pick(tester, 1);
      await tester.tap(find.byTooltip('移除阿瓦隆'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('game-chip-1')), findsNothing);
      await submit(tester, '送出');
      expect(repo.createCalls.single.gameIds, isEmpty);
    });

    testWidgets('沒有符合的遊戲：顯示提示', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      await type(tester, '不存在');
      expect(find.text('找不到符合的遊戲'), findsOneWidget);
    });

    testWidgets('編輯：帶入既有遊戲，儲存時送出 game_ids', (tester) async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 20, 19))],
      );
      await openForm(
        tester,
        repo,
        valid().copyWith(
          games: const [
            GameRef(id: 1, name: '阿瓦隆'),
            GameRef(id: 3, name: '馬可波羅'),
          ],
        ),
        groupId: 'g-1',
      );
      expect(find.byKey(const Key('game-chip-1')), findsOneWidget);
      expect(find.byKey(const Key('game-chip-3')), findsOneWidget);
      await submit(tester, '儲存');
      expect(repo.updateCalls.single.$2['game_ids'], [1, 3]);
    });
  });
}
