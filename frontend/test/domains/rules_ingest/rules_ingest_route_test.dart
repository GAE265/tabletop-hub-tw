// 規則書匯入的網址（spec：add-rules-ingest-page）。
// 原本測參考畫面 /proto/rules-ingest；參考畫面移除後改成測正式頁面與舊網址找不到。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../app/router_test.dart' show goTo, pumpApp;
import 'rules_ingest_page_test.dart' show admin;

void main() {
  testWidgets('/rules-ingest 是規則書匯入正式頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false, user: admin);
    goTo(tester, '/rules-ingest');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules-ingest-page')), findsOneWidget);
  });

  testWidgets('開啟旗標：/proto/rules-ingest 已移除，顯示找不到頁面', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/rules-ingest');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('關閉旗標顯示找不到頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/proto/rules-ingest');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });
}
