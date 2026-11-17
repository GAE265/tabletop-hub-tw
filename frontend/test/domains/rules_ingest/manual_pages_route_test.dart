import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../app/router_test.dart' show goTo, pumpApp;

void main() {
  testWidgets('開啟旗標顯示 rules-ingest 參考畫面', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/rules-ingest');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules-ingest-proto-page')), findsOneWidget);
  });

  testWidgets('關閉旗標顯示找不到頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/proto/rules-ingest');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });
}
