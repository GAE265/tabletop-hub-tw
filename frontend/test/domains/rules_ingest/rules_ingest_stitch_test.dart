// 規則書匯入頁的 Stitch 版面：木紋背景、兩個區塊是有厚度的卡片、按鈕都是厚按鈕、
// 沒有權限的提示也放在卡片上。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/thick_widgets.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';

import '../../support/fakes.dart';
import 'rules_ingest_page_test.dart' show player, pumpPage;

void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder inPage(Finder finder) => find.descendant(
  of: find.byKey(const Key('rules-ingest-page')),
  matching: finder,
);

void main() {
  testWidgets('木紋背景；匯入與已入庫兩個區塊是厚卡片', (tester) async {
    await pumpPage(tester, FakeManualPagesRepository(), FakeImagePicker());
    await tester.pumpAndSettle();
    expect(inPage(find.byType(WoodBackground)), findsOneWidget);
    for (final key in ['rules-ingest-import', 'rules-ingest-stored']) {
      expectThick(
        tester,
        find
            .descendant(
              of: find.byKey(Key(key)),
              matching: find.byType(DecoratedBox),
            )
            .first,
        key,
      );
    }
    expect(inPage(find.byType(Card)), findsNothing);
  });

  testWidgets('按鈕都是厚按鈕（沒有 OutlinedButton）', (tester) async {
    await pumpPage(tester, FakeManualPagesRepository(), FakeImagePicker());
    await tester.pumpAndSettle();
    expect(inPage(find.byType(OutlinedButton)), findsNothing);
    for (final key in [
      'pick-images-button',
      'import-button',
      'read-pages-button',
    ]) {
      expect(
        find.ancestor(
          of: find.byKey(Key(key)),
          matching: find.byType(ThickButton),
        ),
        findsOneWidget,
        reason: key,
      );
    }
  });

  testWidgets('不是管理員：提示放在厚卡片上', (tester) async {
    await pumpPage(
      tester,
      FakeManualPagesRepository(),
      FakeImagePicker(),
      user: player,
    );
    await tester.pumpAndSettle();
    expect(
      find.ancestor(
        of: find.text('只有管理員可以匯入規則書'),
        matching: find.byType(ThickCard),
      ),
      findsOneWidget,
    );
  });
}
