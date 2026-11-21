import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_option.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_search_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
import 'package:tabletop_hub/prototypes/rules_ingest/rules_ingest_proto_page.dart';

import '../../support/fakes.dart';

Future<void> pumpPrototype(
  WidgetTester tester,
  FakeManualPagesRepository repo,
  FakeImagePicker picker, {
  FakeGameSearchRepository? gameRepo,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        manualPagesRepositoryProvider.overrideWithValue(repo),
        imagePickerProvider.overrideWithValue(picker),
        gameSearchRepositoryProvider.overrideWithValue(
          gameRepo ??
              FakeGameSearchRepository(allGames: [
                GameOption(id: 1, name: 'Test Game', englishName: 'test'),
              ]),
        ),
      ],
      child: const MaterialApp(home: RulesIngestProtoPage()),
    ),
  );
}

void main() {
  testWidgets('欄位與按鈕存在，缺欄位禁用匯入', (tester) async {
    await pumpPrototype(tester, FakeManualPagesRepository(), FakeImagePicker());
    // 等 _loadAllGames microtask 完成
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('games-name-input')), findsOneWidget);
    expect(find.byKey(const Key('start-page-input')), findsOneWidget);
    expect(
      tester
          .widget<ElevatedButton>(find.byKey(const Key('import-button')))
          .onPressed,
      isNull,
    );
    // 輸入名稱但未從下拉選取 → canImport 仍為 false
    await tester.enterText(find.byKey(const Key('games-name-input')), 'abc');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('import-button')),
        findsOneWidget); // 匯入按鈕仍在，但 disabled
  });

  testWidgets('讀回空列表與 fake 提示', (tester) async {
    await pumpPrototype(tester, FakeManualPagesRepository(), FakeImagePicker());
    await tester.pumpAndSettle();
    // 選一款遊戲 → 呼叫 selectGame
    // 因為 Autocomplete 的選項來自 allGames，我們用 enterText + 選取
    await tester.enterText(find.byKey(const Key('games-name-input')), 'Test');
    await tester.pumpAndSettle();
    // Autocomplete 會顯示下拉選項 "Test Game"，點選
    await tester.tap(find.text('Test Game').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('read-pages-button')));
    await tester.pumpAndSettle();
    expect(find.text('這款桌遊還沒有規則書頁面'), findsOneWidget);
    expect(find.text('OCR：fake（內容不是真實辨識結果）'), findsOneWidget);
  });

  testWidgets('選圖匯入後自動讀回與顯示 cloud 提示', (tester) async {
    final repo = FakeManualPagesRepository()..ocrProvider = 'cloud';
    final picker = FakeImagePicker()
      ..images = [PickedImage(name: 'sample.png', bytes: Uint8List(1))];
    await pumpPrototype(tester, repo, picker);
    await tester.pumpAndSettle();
    // 選遊戲
    await tester.enterText(find.byKey(const Key('games-name-input')), 'Test');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Test Game').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('pick-images-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('import-button')));
    await tester.pumpAndSettle();
    expect(find.text('成功（索引 3 段）'), findsOneWidget);
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
    await pumpPrototype(tester, repo, FakeImagePicker());
    await tester.pumpAndSettle();
    // 選遊戲
    await tester.enterText(find.byKey(const Key('games-name-input')), 'Test');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Test Game').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('read-pages-button')));
    await tester.pumpAndSettle();
    expect(find.text('（整頁沒文字）'), findsOneWidget);
  });
}
