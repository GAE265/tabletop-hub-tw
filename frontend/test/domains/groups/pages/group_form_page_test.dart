// 正式開團／編輯表單（spec：groups-calendar-page 的「開團與編輯表單」；店家與遊戲的
// 下拉選單見 update-groups-shop-game-pickers）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
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

/// [box] 的外框底邊比上邊粗，而且有陰影（有厚度）。
void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder inKey(String key, Finder f) =>
    find.descendant(of: find.byKey(Key(key)), matching: f);

void main() {
  // Stitch 版面：木紋背景，每個欄位各一張有厚度的卡片
  group('Stitch 版面', () {
    testWidgets('開團：木紋背景，說明卡與每個欄位的卡片都有厚度', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(
        find.descendant(
          of: find.byKey(const Key('group-form-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      for (final key in [
        'group-form-intro',
        'group-form-shop',
        'group-form-title',
        'group-form-time',
        'group-form-capacity',
        'group-form-fee',
        'group-form-games',
        'group-form-description',
      ]) {
        final card = find.byKey(Key(key));
        await tester.ensureVisible(card);
        expectThick(
          tester,
          find.descendant(of: card, matching: find.byType(DecoratedBox)).first,
          key,
        );
      }
    });

    testWidgets('開團說明卡：寫實際流程，不提自動訂位或自動成團', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(inKey('group-form-intro', find.text('發起一場揪團')), findsOneWidget);
      expect(find.textContaining('團務操作'), findsOneWidget);
      expect(find.textContaining('自動'), findsNothing);
      expect(find.textContaining('同步'), findsNothing);
    });

    testWidgets('編輯：沒有開團說明卡', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid(), groupId: 'g-1');
      expect(find.byKey(const Key('group-form-intro')), findsNothing);
    });

    testWidgets('標題與簡介顯示字數（上限 100、2000）', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(inKey('group-form-title', find.text('5／100 字')), findsOneWidget);
      expect(
        inKey('group-form-description', find.text('0／2000 字')),
        findsOneWidget,
      );
      await tester.enterText(
        inKey('group-form-title', find.byType(TextField)),
        '卡坦島',
      );
      await tester.pump();
      expect(inKey('group-form-title', find.text('3／100 字')), findsOneWidget);
    });

    testWidgets('日期與時段卡顯示時數', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(inKey('group-form-time', find.text('2 小時')), findsOneWidget);
    });

    testWidgets('人數用加減按鈕：顯示人數與「開團主 1 人＋募集 N 人」，送出加減後的人數', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      Finder capacity(String text) =>
          inKey('group-form-capacity', find.text(text));
      expect(capacity('4 人'), findsOneWidget);
      expect(capacity('開團主 1 人＋募集 3 人'), findsOneWidget);
      final plus = find.byKey(const Key('group-capacity-plus'));
      await tester.ensureVisible(plus);
      await tester.tap(plus);
      await tester.pump();
      expect(capacity('5 人'), findsOneWidget);
      await submit(tester, '送出');
      expect(repo.createCalls.single.capacity, 5);
    });

    testWidgets('人數最少 2 人：到 2 人時「－」停用', (tester) async {
      final data = valid();
      await openForm(
        tester,
        FakeGroupsRepository(),
        GroupFormData(
          shopId: data.shopId,
          title: data.title,
          date: data.date,
          startTime: data.startTime,
          endTime: data.endTime,
          capacity: '2',
        ),
      );
      final minus = find.byKey(const Key('group-capacity-minus'));
      await tester.ensureVisible(minus);
      expect(tester.widget<IconButton>(minus).onPressed, isNull);
    });

    testWidgets('新開團沒填人數：預設 4 人', (tester) async {
      await openForm(tester, FakeGroupsRepository(), GroupFormData(date: day));
      expect(inKey('group-form-capacity', find.text('4 人')), findsOneWidget);
    });

    testWidgets('費用卡說明 0 元代表免費', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(
        inKey('group-form-fee', find.textContaining('0 代表免費')),
        findsOneWidget,
      );
    });

    testWidgets('送出是有厚度的大按鈕，下方沒有重複的提醒', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      final button = find.ancestor(
        of: find.text('送出'),
        matching: find.byType(DecoratedBox),
      );
      await tester.ensureVisible(find.text('送出'));
      expectThick(tester, button.first);
      // 說明卡已經提醒過開團後在哪裡修改，按鈕下方不再重複
      expect(find.textContaining('送出後可以'), findsNothing);
    });
  });

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

  group('遊戲下拉選單（可搜尋、可複選）', () {
    final field = find.byKey(const Key('game-picker-field'));
    final search = find.byKey(const Key('game-search-input'));

    Future<void> open(WidgetTester tester) async {
      await tester.ensureVisible(field);
      await tester.tap(field);
      await tester.pumpAndSettle();
    }

    Future<void> toggle(WidgetTester tester, int id) async {
      final option = find.byKey(Key('game-option-$id'));
      await tester.ensureVisible(option);
      await tester.tap(option);
      await tester.pumpAndSettle();
    }

    bool checked(WidgetTester tester, int id) => tester
        .widget<CheckboxListTile>(find.byKey(Key('game-option-$id')))
        .value!;

    testWidgets('點欄位展開全部遊戲，再點一次收起', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      expect(find.byKey(const Key('game-option-1')), findsNothing);
      await open(tester);
      for (final id in [1, 2, 3]) {
        expect(find.byKey(Key('game-option-$id')), findsOneWidget);
      }
      await open(tester);
      expect(find.byKey(const Key('game-option-1')), findsNothing);
    });

    testWidgets('勾選兩款：依勾選順序顯示標籤，送出 game_ids', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      await open(tester);
      await toggle(tester, 3);
      await toggle(tester, 1);
      expect(checked(tester, 3), isTrue);
      expect(checked(tester, 1), isTrue);
      expect(checked(tester, 2), isFalse);
      expect(
        tester.getTopLeft(find.byKey(const Key('game-chip-3'))).dx,
        lessThan(tester.getTopLeft(find.byKey(const Key('game-chip-1'))).dx),
      );
      await submit(tester, '送出');
      expect(repo.createCalls.single.gameIds, [3, 1]);
    });

    testWidgets('搜尋框篩選清單，不呼叫 API', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      await open(tester);
      await tester.enterText(search, '阿');
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('game-option-1')), findsOneWidget);
      expect(find.byKey(const Key('game-option-2')), findsOneWidget);
      expect(find.byKey(const Key('game-option-3')), findsNothing);
      expect(repo.gamesCalls, 1);
    });

    testWidgets('沒有符合的遊戲：顯示提示', (tester) async {
      await openForm(tester, FakeGroupsRepository(), valid());
      await open(tester);
      await tester.enterText(search, '不存在');
      await tester.pumpAndSettle();
      expect(find.text('找不到符合的遊戲'), findsOneWidget);
    });

    testWidgets('取消勾選或按標籤的 ✕：移除該遊戲', (tester) async {
      final repo = FakeGroupsRepository();
      await openForm(tester, repo, valid());
      await open(tester);
      await toggle(tester, 1);
      await toggle(tester, 3);
      await toggle(tester, 1);
      expect(find.byKey(const Key('game-chip-1')), findsNothing);
      await tester.tap(find.byTooltip('移除馬可波羅'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('game-chip-3')), findsNothing);
      expect(checked(tester, 3), isFalse);
      await submit(tester, '送出');
      expect(repo.createCalls.single.gameIds, isEmpty);
    });

    testWidgets('遊戲清單載入失敗：顯示錯誤與「重試」', (tester) async {
      final repo = FakeGroupsRepository()
        ..gamesError = const ApiException(
          code: 'NETWORK_ERROR',
          message: '遊戲清單載入失敗',
        );
      await openForm(tester, repo, valid());
      await open(tester);
      expect(find.text('遊戲清單載入失敗'), findsOneWidget);
      repo.gamesError = null;
      await tester.tap(find.text('重試').last);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('game-option-1')), findsOneWidget);
    });

    testWidgets('編輯：帶入既有遊戲，標籤與勾選狀態正確，儲存時送出 game_ids', (tester) async {
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
      await open(tester);
      expect(checked(tester, 1), isTrue);
      expect(checked(tester, 2), isFalse);
      await submit(tester, '儲存');
      expect(repo.updateCalls.single.$2['game_ids'], [1, 3]);
    });
  });

  testWidgets('日期只能選今天以後；編輯過去日期的揪團，初始日期為今天', (tester) async {
    await openForm(
      tester,
      FakeGroupsRepository(),
      GroupFormData(date: DateTime(2026, 11, 1)),
      groupId: 'g-1',
    );
    await tester.tap(find.text('2026/11/1'));
    await tester.pumpAndSettle();
    final picker = tester.widget<DatePickerDialog>(
      find.byType(DatePickerDialog),
    );
    expect(picker.firstDate, DateTime(2026, 11, 14));
    expect(picker.initialDate, DateTime(2026, 11, 14));
  });
}
