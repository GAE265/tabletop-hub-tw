// 規則教學正式頁面（spec：openspec/changes/add-rules-qa/specs/rules-qa-page）。
// 對話邏輯已由 state 測試涵蓋，這裡確認畫面有正確呈現 state，以及 RWD。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/platform/lesson_video_player.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/rules_lesson_page.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/rules_lessons_page.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_chat_state.dart';

import '../../../support/fakes.dart';
import '../support.dart';

final input = find.byKey(const Key('rules-input'));
final sendButton = find.byKey(const Key('rules-send'));
final video = find.byKey(const Key('fake-video-player'));
final chatPanel = find.byKey(const Key('rules-chat'));

Future<FakeRulesQaRepository> pumpPage(
  WidgetTester tester,
  Widget page, {
  FakeRulesQaRepository? repo,
  Size size = const Size(400, 900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = repo ?? sampleRepo();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        rulesQaRepositoryProvider.overrideWithValue(fake),
        lessonVideoPlayerProvider.overrideWithValue(
          const FakeLessonVideoPlayer(),
        ),
      ],
      child: MaterialApp(
        theme: buildAppTheme(const FakeAppFonts()),
        home: page,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return fake;
}

void main() {
  group('遊戲清單', () {
    testWidgets('列出遊戲，有影片的標示「有教學影片」', (tester) async {
      await pumpPage(tester, const RulesLessonsPage());
      expect(find.text('有影片的桌遊'), findsOneWidget);
      expect(find.text('只有規則書的桌遊'), findsOneWidget);
      expect(find.text('有教學影片'), findsOneWidget);
    });

    testWidgets('沒有任何教材：顯示提示', (tester) async {
      await pumpPage(
        tester,
        const RulesLessonsPage(),
        repo: sampleRepo()..lessons = [],
      );
      expect(find.text('目前還沒有可以教學的遊戲'), findsOneWidget);
    });

    testWidgets('載入失敗：顯示錯誤，按「重試」後恢復', (tester) async {
      final repo = sampleRepo()
        ..listError = const ApiException(
          code: 'NETWORK_ERROR',
          message: '無法連線',
        );
      await pumpPage(tester, const RulesLessonsPage(), repo: repo);
      expect(find.text('無法連線'), findsOneWidget);
      repo.listError = null;
      await tester.tap(find.text('重試'));
      await tester.pumpAndSettle();
      expect(find.text('有影片的桌遊'), findsOneWidget);
    });
  });

  group('教學頁', () {
    testWidgets('有影片：先播影片，按「看完了，開始提問」才出現問答', (tester) async {
      await pumpPage(tester, const RulesLessonPage(gameId: 1));
      expect(video, findsOneWidget);
      expect(find.text('影片：abc123'), findsOneWidget);
      expect(input, findsNothing);

      await tester.tap(find.text('看完了，開始提問'));
      await tester.pumpAndSettle();
      expect(input, findsOneWidget);
      expect(video, findsOneWidget);
    });

    testWidgets('沒有影片：直接顯示問答與提示', (tester) async {
      await pumpPage(tester, const RulesLessonPage(gameId: 2));
      expect(video, findsNothing);
      expect(find.text('這款遊戲還沒有教學影片，可以直接問規則'), findsOneWidget);
      expect(input, findsOneWidget);
    });

    testWidgets('只有影片、沒有規則書：不能提問', (tester) async {
      await pumpPage(tester, const RulesLessonPage(gameId: 3));
      await tester.tap(find.text('看完了，開始提問'));
      await tester.pumpAndSettle();
      expect(find.text('這款遊戲的規則書還沒入庫，暫時無法提問'), findsOneWidget);
      expect(input, findsNothing);
    });

    testWidgets('遊戲沒有教材：顯示後端訊息與「回到遊戲清單」', (tester) async {
      await pumpPage(tester, const RulesLessonPage(gameId: 9));
      expect(find.text('這款遊戲還沒有教材'), findsOneWidget);
      expect(find.text('回到遊戲清單'), findsOneWidget);
    });
  });

  group('問答', () {
    testWidgets('點建議問題：送出中顯示「正在查規則…」，回答附頁碼', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      await tester.tap(find.text('一個回合可以做什麼？'));
      await tester.pump();
      expect(find.text('正在查規則…'), findsOneWidget);
      expect(tester.widget<IconButton>(sendButton).onPressed, isNull);

      repo.respond(answer(text: '每個回合抽兩張牌。', pages: [5, 7]));
      await tester.pumpAndSettle();
      expect(find.text('每個回合抽兩張牌。'), findsOneWidget);
      expect(find.text('規則書第 5 頁'), findsOneWidget);
      expect(find.text('規則書第 7 頁'), findsOneWidget);
    });

    testWidgets('輸入問題按送出', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      expect(tester.widget<IconButton>(sendButton).onPressed, isNull);
      await tester.enterText(input, '怎麼計分？');
      await tester.pumpAndSettle();
      await tester.tap(sendButton);
      await tester.pump();
      expect(repo.requests.single.$2.content, '怎麼計分？');
      repo.respond(answer());
      await tester.pumpAndSettle();
    });

    testWidgets('找不到答案：沒有頁碼', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      await tester.tap(find.text('怎麼開始一局？'));
      await tester.pump();
      repo.respond(
        answer(text: '規則書中找不到，建議詢問店員。', answerable: false, pages: []),
      );
      await tester.pumpAndSettle();
      expect(find.text('規則書中找不到，建議詢問店員。'), findsOneWidget);
      expect(find.textContaining('規則書第'), findsNothing);
    });

    testWidgets('送出失敗：顯示後端訊息，問題回到輸入框', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      await tester.tap(find.text('怎麼開始一局？'));
      await tester.pump();
      repo.fail(
        const ApiException(
          code: 'RULES_QA_UNAVAILABLE',
          message: '規則問答暫時無法使用，請稍後再試',
          statusCode: 503,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('規則問答暫時無法使用，請稍後再試'), findsOneWidget);
      expect(tester.widget<TextField>(input).controller!.text, '怎麼開始一局？');
    });

    testWidgets('對話已失效：提示並清空', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      await tester.tap(find.text('怎麼開始一局？'));
      await tester.pump();
      repo.fail(
        const ApiException(
          code: rulesQaConversationNotFoundCode,
          message: '對話已過期',
          statusCode: 404,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('對話已過期，已為你開始新對話'), findsOneWidget);
    });

    testWidgets('開始新對話：清空對話，建議問題回來', (tester) async {
      final repo = await pumpPage(tester, const RulesLessonPage(gameId: 2));
      await tester.tap(find.text('怎麼開始一局？'));
      await tester.pump();
      repo.respond(answer(text: '先發五張牌。'));
      await tester.pumpAndSettle();
      expect(find.text('一個回合可以做什麼？'), findsNothing);

      await tester.tap(find.text('開始新對話'));
      await tester.pumpAndSettle();
      expect(find.text('先發五張牌。'), findsNothing);
      expect(find.text('一個回合可以做什麼？'), findsOneWidget);
    });
  });

  group('RWD', () {
    Future<void> openChat(WidgetTester tester, Size size) async {
      await pumpPage(tester, const RulesLessonPage(gameId: 1), size: size);
      await tester.tap(find.text('看完了，開始提問'));
      await tester.pumpAndSettle();
    }

    testWidgets('手機寬度（360）：影片在上、問答在下，沒有溢出', (tester) async {
      await openChat(tester, const Size(360, 800));
      expect(
        tester.getTopLeft(chatPanel).dy,
        greaterThanOrEqualTo(tester.getBottomLeft(video).dy),
      );
    });

    testWidgets('桌機寬度（1280）：影片與問答左右並排', (tester) async {
      await openChat(tester, const Size(1280, 900));
      expect(
        tester.getTopLeft(chatPanel).dx,
        greaterThanOrEqualTo(tester.getTopRight(video).dx),
      );
    });
  });
}
