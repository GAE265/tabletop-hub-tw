// 規則書匯入正式頁面（spec：add-rules-ingest-page 的 rules-ingest-page）。
// 前四個情境原本測參考畫面（RulesIngestProtoPage），參考畫面移除後改測正式頁面，情境不變。
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_option.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_search_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/pages/rules_ingest_page.dart';

import '../../support/fakes.dart';

const admin = DevUser(id: 'u-admin', displayName: '測試管理員', role: 'admin');
const player = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');
const staff = DevUser(
  id: 'u-staff',
  displayName: '測試店家人員',
  role: 'shop_staff',
  shopId: 's-b',
);

Future<FakeGameSearchRepository> pumpPage(
  WidgetTester tester,
  FakeManualPagesRepository repo,
  FakeImagePicker picker, {
  FakeGameSearchRepository? gameRepo,
  DevUser? user = admin,
  Size size = const Size(400, 900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final games =
      gameRepo ??
      FakeGameSearchRepository(
        allGames: [GameOption(id: 1, name: 'Test Game', englishName: 'test')],
      );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        manualPagesRepositoryProvider.overrideWithValue(repo),
        imagePickerProvider.overrideWithValue(picker),
        gameSearchRepositoryProvider.overrideWithValue(games),
        currentDevUserProvider.overrideWithValue(user),
      ],
      child: MaterialApp(
        theme: buildAppTheme(const FakeAppFonts()),
        home: const RulesIngestPage(),
      ),
    ),
  );
  return games;
}

VoidCallback? onPressed(WidgetTester tester, String key) =>
    tester.widget<ButtonStyleButton>(find.byKey(Key(key))).onPressed;

Future<void> selectGame(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('games-name-input')), 'Test');
  await tester.pumpAndSettle();
  await tester.tap(find.text('Test Game').last);
  await tester.pumpAndSettle();
}

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

PickedImage image(String name) => PickedImage(name: name, bytes: Uint8List(1));

void main() {
  testWidgets('欄位與按鈕存在，缺欄位禁用匯入', (tester) async {
    await pumpPage(tester, FakeManualPagesRepository(), FakeImagePicker());
    // 等 _loadAllGames microtask 完成
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('games-name-input')), findsOneWidget);
    expect(find.byKey(const Key('start-page-input')), findsOneWidget);
    expect(onPressed(tester, 'import-button'), isNull);
    // 輸入名稱但未從下拉選取 → canImport 仍為 false
    await tester.enterText(find.byKey(const Key('games-name-input')), 'abc');
    await tester.pumpAndSettle();
    expect(onPressed(tester, 'import-button'), isNull);
  });

  testWidgets('讀回空列表與 fake 提示', (tester) async {
    await pumpPage(tester, FakeManualPagesRepository(), FakeImagePicker());
    await tester.pumpAndSettle();
    expect(find.text('請先讀回，確認目前 OCR 實作；cloud 匯入會產生費用'), findsOneWidget);
    await selectGame(tester);
    await tapKey(tester, 'read-pages-button');
    expect(find.text('這款桌遊還沒有規則書頁面'), findsOneWidget);
    expect(find.text('OCR：fake（內容不是真實辨識結果）'), findsOneWidget);
  });

  testWidgets('選圖匯入後自動讀回與顯示 cloud 提示', (tester) async {
    final repo = FakeManualPagesRepository()..ocrProvider = 'cloud';
    final picker = FakeImagePicker()..images = [image('sample.png')];
    await pumpPage(tester, repo, picker);
    await tester.pumpAndSettle();
    await selectGame(tester);
    await tapKey(tester, 'pick-images-button');
    await tapKey(tester, 'import-button');
    expect(find.text('成功'), findsOneWidget);
    expect(repo.lists, [1]);
    await tester.scrollUntilVisible(
      find.text('OCR：cloud'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('OCR：cloud'), findsOneWidget);
    expect(find.text('使用雲端 OCR 匯入會產生費用'), findsOneWidget);
  });

  testWidgets('空文字顯示整頁沒文字', (tester) async {
    final repo = FakeManualPagesRepository()..rows[1] = '';
    await pumpPage(tester, repo, FakeImagePicker());
    await tester.pumpAndSettle();
    await selectGame(tester);
    await tapKey(tester, 'read-pages-button');
    expect(find.text('（整頁沒文字）'), findsOneWidget);
  });

  group('權限（add-rules-ingest-page）', () {
    for (final user in [player, staff]) {
      testWidgets('${user.role}：顯示只有管理員可以匯入，不載入遊戲清單', (tester) async {
        final games = await pumpPage(
          tester,
          FakeManualPagesRepository(),
          FakeImagePicker(),
          user: user,
        );
        await tester.pumpAndSettle();
        expect(find.text('只有管理員可以匯入規則書'), findsOneWidget);
        expect(find.byKey(const Key('games-name-input')), findsNothing);
        expect(games.listAllCalls, 0);
      });
    }

    testWidgets('管理員：載入遊戲清單', (tester) async {
      final games = await pumpPage(
        tester,
        FakeManualPagesRepository(),
        FakeImagePicker(),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('rules-ingest-page')), findsOneWidget);
      expect(games.listAllCalls, 1);
    });
  });

  group('匯入（add-rules-ingest-page）', () {
    testWidgets('起始頁碼 0：顯示提示，匯入停用', (tester) async {
      final picker = FakeImagePicker()..images = [image('a.png')];
      await pumpPage(tester, FakeManualPagesRepository(), picker);
      await tester.pumpAndSettle();
      await selectGame(tester);
      await tapKey(tester, 'pick-images-button');
      expect(onPressed(tester, 'import-button'), isNotNull);

      await tester.enterText(find.byKey(const Key('start-page-input')), '0');
      await tester.pumpAndSettle();
      expect(find.text('起始頁碼必須大於或等於 1'), findsOneWidget);
      expect(onPressed(tester, 'import-button'), isNull);
    });

    testWidgets('選兩張圖：依檔名列出與頁碼；移除第一張後頁碼往前', (tester) async {
      final picker = FakeImagePicker()
        ..images = [image('b.png'), image('a.png')];
      await pumpPage(tester, FakeManualPagesRepository(), picker);
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('start-page-input')), '3');
      await tester.pumpAndSettle();
      await tapKey(tester, 'pick-images-button');
      expect(find.text('a.png'), findsOneWidget);
      expect(find.text('→ 匯入為第 3 頁'), findsOneWidget);
      expect(find.text('→ 匯入為第 4 頁'), findsOneWidget);
      expect(
        tester.getTopLeft(find.text('a.png')).dy,
        lessThan(tester.getTopLeft(find.text('b.png')).dy),
      );

      await tapKey(tester, 'remove-image-0');
      expect(find.text('a.png'), findsNothing);
      expect(find.text('b.png'), findsOneWidget);
      expect(find.text('→ 匯入為第 3 頁'), findsOneWidget);
      expect(find.text('→ 匯入為第 4 頁'), findsNothing);
    });

    testWidgets('單頁失敗：該頁顯示錯誤，其他頁照常匯入', (tester) async {
      final repo = FakeManualPagesRepository()
        ..failures[2] = const ApiException(
          code: 'OCR_UNAVAILABLE',
          message: 'OCR 服務暫時無法使用',
          statusCode: 503,
        );
      final picker = FakeImagePicker()
        ..images = [image('1.png'), image('2.png'), image('3.png')];
      await pumpPage(tester, repo, picker);
      await tester.pumpAndSettle();
      await selectGame(tester);
      await tapKey(tester, 'pick-images-button');
      await tapKey(tester, 'import-button');
      expect(repo.imports.map((i) => i.page), [1, 2, 3]);
      expect(find.text('第 2 頁：2.png'), findsOneWidget);
      expect(find.text('OCR 服務暫時無法使用'), findsOneWidget);
      expect(find.text('成功'), findsNWidgets(2));
    });
  });

  group('版面（add-rules-ingest-page）', () {
    testWidgets('手機：已入庫頁面在匯入區下方', (tester) async {
      await pumpPage(tester, FakeManualPagesRepository(), FakeImagePicker());
      await tester.pumpAndSettle();
      final import = tester.getRect(
        find.byKey(const Key('rules-ingest-import')),
      );
      final stored = tester.getRect(
        find.byKey(const Key('rules-ingest-stored')),
      );
      expect(stored.top, greaterThanOrEqualTo(import.bottom));
    });

    testWidgets('桌機：已入庫頁面在匯入區右側', (tester) async {
      await pumpPage(
        tester,
        FakeManualPagesRepository(),
        FakeImagePicker(),
        size: const Size(1280, 800),
      );
      await tester.pumpAndSettle();
      final import = tester.getRect(
        find.byKey(const Key('rules-ingest-import')),
      );
      final stored = tester.getRect(
        find.byKey(const Key('rules-ingest-stored')),
      );
      expect(stored.left, greaterThanOrEqualTo(import.right));
    });
  });
}
