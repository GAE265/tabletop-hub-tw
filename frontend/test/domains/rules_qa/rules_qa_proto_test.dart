// 參考畫面的 widget 測試：後端完成前無法手動走一遍，先用 fake repository 確認畫面接上 state。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';
import 'package:tabletop_hub/prototypes/rules_qa/rules_lesson_proto_page.dart';
import 'package:tabletop_hub/prototypes/rules_qa/rules_qa_proto_page.dart';

import '../../support/fakes.dart';
import 'support.dart';

Future<FakeRulesQaRepository> pump(WidgetTester tester, Widget home) async {
  final repo = sampleRepo();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [rulesQaRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(home: home),
    ),
  );
  await tester.pumpAndSettle();
  return repo;
}

void main() {
  testWidgets('清單：列出遊戲，有影片的標示「有教學影片」', (tester) async {
    await pump(tester, const RulesQaProtoPage());
    expect(find.text('有影片的桌遊'), findsOneWidget);
    expect(find.text('只有規則書的桌遊'), findsOneWidget);
    expect(find.text('有教學影片'), findsOneWidget);
  });

  testWidgets('清單是空的：顯示提示', (tester) async {
    final repo = sampleRepo()..lessons = [];
    await tester.pumpWidget(
      ProviderScope(
        overrides: [rulesQaRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: RulesQaProtoPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('目前還沒有可以教學的遊戲'), findsOneWidget);
  });

  testWidgets('有影片：先顯示影片與「看完了，開始提問」，按下後出現問答', (tester) async {
    await pump(tester, const RulesLessonProtoPage(gameId: 1));
    expect(find.text('測試桌遊規則教學'), findsOneWidget);
    expect(find.text('看完了，開始提問'), findsOneWidget);
    expect(find.byKey(const Key('rules_qa-input')), findsNothing);

    await tester.tap(find.text('看完了，開始提問'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules_qa-input')), findsOneWidget);
    expect(find.text('怎麼開始一局？'), findsOneWidget);
  });

  testWidgets('沒有影片：直接顯示問答與提示', (tester) async {
    await pump(tester, const RulesLessonProtoPage(gameId: 2));
    expect(find.text('這款遊戲還沒有教學影片，可以直接問規則'), findsOneWidget);
    expect(find.byKey(const Key('rules_qa-input')), findsOneWidget);
  });

  testWidgets('只有影片、沒有規則書：不能提問', (tester) async {
    await pump(tester, const RulesLessonProtoPage(gameId: 3));
    await tester.tap(find.text('看完了，開始提問'));
    await tester.pumpAndSettle();
    expect(find.text('這款遊戲的規則書還沒入庫，暫時無法提問'), findsOneWidget);
    expect(find.byKey(const Key('rules_qa-input')), findsNothing);
  });

  testWidgets('點建議問題直接送出，回答下方顯示頁碼', (tester) async {
    final repo = await pump(tester, const RulesLessonProtoPage(gameId: 2));
    await tester.tap(find.text('一個回合可以做什麼？'));
    await tester.pump();
    expect(find.text('正在查規則…'), findsOneWidget);
    repo.respond(answer(text: '每個回合抽兩張牌。', pages: [5]));
    await tester.pumpAndSettle();
    expect(repo.requests.single.$2.content, '一個回合可以做什麼？');
    expect(find.text('每個回合抽兩張牌。'), findsOneWidget);
    expect(find.text('規則書第 5 頁'), findsOneWidget);
  });
}
