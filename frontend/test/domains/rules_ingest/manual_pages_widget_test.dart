import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
import 'package:tabletop_hub/prototypes/rules_ingest/rules_ingest_proto_page.dart';

import '../../support/fakes.dart';

Future<void> pumpPrototype(
  WidgetTester tester,
  FakeManualPagesRepository repo,
  FakeImagePicker picker,
) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        manualPagesRepositoryProvider.overrideWithValue(repo),
        imagePickerProvider.overrideWithValue(picker),
      ],
      child: const MaterialApp(home: RulesIngestProtoPage()),
    ),
  );
}

void main() {
  testWidgets('欄位與按鈕存在，缺欄位禁用匯入', (tester) async {
    await pumpPrototype(tester, FakeManualPagesRepository(), FakeImagePicker());
    expect(find.byKey(const Key('games-id-input')), findsOneWidget);
    expect(find.byKey(const Key('start-page-input')), findsOneWidget);
    expect(
      tester
          .widget<ElevatedButton>(find.byKey(const Key('import-button')))
          .onPressed,
      isNull,
    );
    await tester.enterText(find.byKey(const Key('games-id-input')), 'abc');
    await tester.pump();
    expect(find.text('桌遊編號必須是正整數'), findsOneWidget);
  });

  testWidgets('讀回空列表與 fake 提示', (tester) async {
    await pumpPrototype(tester, FakeManualPagesRepository(), FakeImagePicker());
    await tester.enterText(find.byKey(const Key('games-id-input')), '1');
    await tester.pump();
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
    await tester.enterText(find.byKey(const Key('games-id-input')), '1');
    await tester.tap(find.byKey(const Key('pick-images-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('import-button')));
    await tester.pumpAndSettle();
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
    await pumpPrototype(tester, repo, FakeImagePicker());
    await tester.enterText(find.byKey(const Key('games-id-input')), '1');
    await tester.pump();
    await tester.tap(find.byKey(const Key('read-pages-button')));
    await tester.pumpAndSettle();
    expect(find.text('（整頁沒文字）'), findsOneWidget);
  });
}
