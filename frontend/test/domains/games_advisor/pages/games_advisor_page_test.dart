// 推薦 Agent 正式頁面（交接說明：docs/handoff/games_advisor.md 第 2、3 節）。
// 對話邏輯已由 advisor_state_test 涵蓋，這裡只確認畫面有正確呈現 state。
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
import 'package:tabletop_hub/domains/games_advisor/pages/games_advisor_page.dart';
import 'package:tabletop_hub/domains/games_advisor/state/advisor_state.dart';
import 'package:tabletop_hub/domains/games_advisor/state/game_card_text.dart';

import '../../../support/fakes.dart';

const avalon = AdvisorGame(
  id: 4,
  name: '阿瓦隆',
  minPlayers: 5,
  maxPlayers: 10,
  minPlaytime: 30,
  maxPlaytime: 30,
  minAge: 13,
  weight: 1.8,
);

const animals = AdvisorGame(
  id: 9,
  name: '動物疊疊樂',
  minPlayers: 2,
  maxPlayers: 4,
  minPlaytime: 15,
  maxPlaytime: 15,
  minAge: 4,
  weight: 1,
);

AdvisorMessageResponse cards({RelaxedConstraint? relaxed}) =>
    AdvisorMessageResponse(
      responseId: 'r-1',
      reply: '這兩款都適合輕鬆聊天。',
      relaxedConstraint: relaxed,
      recommendations: const [
        AdvisorRecommendation(
          game: avalon,
          reason: '陣營推理，邊玩邊聊。',
          excerpts: [
            AdvisorExcerpt(id: 'e-1', text: '大家一直互相懷疑，超好笑。', language: 'zh'),
            AdvisorExcerpt(
              id: 'e-2',
              text: 'Great social deduction.',
              language: 'en',
            ),
          ],
        ),
        AdvisorRecommendation(game: animals, reason: '規則簡單。', excerpts: []),
      ],
    );

const textOnly = AdvisorMessageResponse(
  responseId: 'r-1',
  reply: '你們大概想玩多久呢？',
  relaxedConstraint: null,
  recommendations: [],
);

final input = find.byKey(const Key('advisor-input'));
final sendButton = find.byKey(const Key('advisor-send'));
final newButton = find.byKey(const Key('advisor-new'));

Future<FakeAdvisorRepository> pumpPage(
  WidgetTester tester, {
  Size size = const Size(400, 900),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final repo = FakeAdvisorRepository();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [advisorRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: buildAppTheme(const FakeAppFonts()),
        home: const GamesAdvisorPage(),
      ),
    ),
  );
  return repo;
}

bool enabled(WidgetTester tester, Finder finder) {
  final widget = tester.widget(finder);
  return switch (widget) {
    ButtonStyleButton() => widget.onPressed != null,
    IconButton() => widget.onPressed != null,
    TextField() => widget.enabled ?? true,
    _ => throw ArgumentError('不認得的元件：$widget'),
  };
}

String inputText(WidgetTester tester) =>
    tester.widget<TextField>(input).controller!.text;

/// 送出一句話並讓後端回應。
Future<void> ask(
  WidgetTester tester,
  FakeAdvisorRepository repo,
  String text,
  AdvisorMessageResponse response,
) async {
  await tester.enterText(input, text);
  await tester.tap(sendButton);
  await tester.pump();
  repo.respond(response);
  await tester.pumpAndSettle();
}

void main() {
  group('空畫面', () {
    testWidgets('說明文字、3 個範例，「開始新對話」停用', (tester) async {
      await pumpPage(tester);
      expect(find.byKey(const Key('games-advisor-page')), findsOneWidget);
      expect(find.text('我幫你挑桌遊'), findsOneWidget);
      for (final example in ['我們 4 個人，想輕鬆聊天', '2 個人約會玩', '6 個人，30 分鐘內玩完']) {
        expect(find.text(example), findsOneWidget);
      }
      expect(enabled(tester, newButton), isFalse);
    });

    testWidgets('點範例直接送出', (tester) async {
      final repo = await pumpPage(tester);
      await tester.tap(find.text('2 個人約會玩'));
      await tester.pump();
      expect(repo.requests.single.content, '2 個人約會玩');
      repo.respond(textOnly);
      await tester.pumpAndSettle();
    });
  });

  group('對話', () {
    testWidgets('送出中：顯示「正在找桌遊…」，輸入與按鈕都停用', (tester) async {
      final repo = await pumpPage(tester);
      await tester.enterText(input, '我們 4 個人');
      await tester.tap(sendButton);
      await tester.pump();
      expect(find.text('正在找桌遊…'), findsOneWidget);
      expect(find.text('我們 4 個人'), findsOneWidget);
      expect(enabled(tester, input), isFalse);
      expect(enabled(tester, sendButton), isFalse);
      expect(enabled(tester, newButton), isFalse);

      repo.respond(textOnly);
      await tester.pumpAndSettle();
      expect(find.text('正在找桌遊…'), findsNothing);
    });

    testWidgets('追問：只有文字，沒有卡片', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', textOnly);
      expect(find.text('你們大概想玩多久呢？'), findsOneWidget);
      expect(find.byKey(const Key('advisor-game-card')), findsNothing);
    });

    testWidgets('推薦卡片：名稱、資訊行、理由；片段預設摺疊', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', cards());
      expect(find.byKey(const Key('advisor-game-card')), findsNWidgets(2));
      expect(find.text('阿瓦隆'), findsOneWidget);
      expect(find.text(gameMetaText(avalon)), findsOneWidget);
      expect(find.text('陣營推理，邊玩邊聊。'), findsOneWidget);
      expect(find.text('心得片段（2）'), findsOneWidget);
      expect(find.text('大家一直互相懷疑，超好笑。'), findsNothing);
    });

    testWidgets('點開心得片段：顯示原文，英文片段標「英文」', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', cards());
      await tester.tap(find.text('心得片段（2）'));
      await tester.pumpAndSettle();
      expect(find.text('大家一直互相懷疑，超好笑。'), findsOneWidget);
      expect(find.text('Great social deduction.'), findsOneWidget);
      expect(find.text('英文'), findsOneWidget);
    });

    testWidgets('沒有心得片段時不顯示那一行', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', cards());
      expect(find.textContaining('心得片段'), findsOneWidget);
    });

    testWidgets('放寬提示：整則訊息只出現一次', (tester) async {
      final repo = await pumpPage(tester);
      await ask(
        tester,
        repo,
        '我們 4 個人',
        cards(relaxed: RelaxedConstraint.playtime),
      );
      expect(
        find.text(relaxedConstraintText(RelaxedConstraint.playtime)),
        findsOneWidget,
      );
    });

    testWidgets('開始新對話：清空，回到空畫面', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', textOnly);
      expect(enabled(tester, newButton), isTrue);
      await tester.tap(newButton);
      await tester.pumpAndSettle();
      expect(find.text('你們大概想玩多久呢？'), findsNothing);
      expect(find.text('我幫你挑桌遊'), findsOneWidget);
    });
  });

  group('錯誤', () {
    testWidgets('對話已失效：畫面清空，提示並把那句放回輸入框', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', textOnly);
      await tester.enterText(input, '那 2 個人呢');
      await tester.tap(sendButton);
      await tester.pump();
      repo.fail(
        const ApiException(
          code: advisorConversationNotFoundCode,
          message: '對話已過期，請重新開始',
          statusCode: 404,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('對話已失效，請開始新對話'), findsOneWidget);
      expect(find.text('你們大概想玩多久呢？'), findsNothing);
      expect(inputText(tester), '那 2 個人呢');
    });

    testWidgets('暫時無法回應：保留前面的對話，那句放回輸入框', (tester) async {
      final repo = await pumpPage(tester);
      await ask(tester, repo, '我們 4 個人', textOnly);
      await tester.enterText(input, '那 2 個人呢');
      await tester.tap(sendButton);
      await tester.pump();
      repo.fail(
        const ApiException(
          code: 'GAMES_ADVISOR_UNAVAILABLE',
          message: '推薦服務暫時無法使用',
          statusCode: 503,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('推薦 Agent 暫時無法回應，請再送一次'), findsOneWidget);
      expect(find.text('你們大概想玩多久呢？'), findsOneWidget);
      expect(inputText(tester), '那 2 個人呢');
    });
  });

  group('輸入框', () {
    testWidgets('顯示字數；空白時不能送出', (tester) async {
      await pumpPage(tester);
      expect(enabled(tester, sendButton), isFalse);
      await tester.enterText(input, '我們 4 個人');
      await tester.pump();
      expect(
        find.textContaining('7 / $advisorMaxContentLength 字'),
        findsOneWidget,
      );
      expect(enabled(tester, sendButton), isTrue);
    });

    testWidgets('Enter 送出', (tester) async {
      final repo = await pumpPage(tester);
      await tester.enterText(input, '我們 4 個人');
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pump();
      expect(repo.requests.single.content, '我們 4 個人');
      repo.respond(textOnly);
      await tester.pumpAndSettle();
    });

    testWidgets('Shift+Enter 不送出', (tester) async {
      final repo = await pumpPage(tester);
      await tester.enterText(input, '我們 4 個人');
      await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await tester.pump();
      expect(repo.requests, isEmpty);
    });
  });

  group('RWD', () {
    testWidgets('手機寬度（360）有卡片時沒有溢出', (tester) async {
      final repo = await pumpPage(tester, size: const Size(360, 800));
      await ask(tester, repo, '我們 4 個人', cards());
      expect(find.byKey(const Key('advisor-game-card')), findsWidgets);
    });

    testWidgets('桌機寬度（1280）：對話區限制寬度並置中', (tester) async {
      await pumpPage(tester, size: const Size(1280, 900));
      final column = tester.getRect(find.byKey(const Key('advisor-column')));
      expect(column.width, lessThan(1280));
      expect(column.center.dx, closeTo(640, 1));
    });
  });
}
