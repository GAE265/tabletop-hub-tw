// 規則教學頁的 AI 語音主持入口：只有支援的遊戲（血與刃的白薔薇）才有，點了進 /host。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/platform/lesson_video_player.dart';
import 'package:tabletop_hub/domains/host/state/host_labels.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/rules_lesson_page.dart';

import '../../../support/fakes.dart';
import '../support.dart';

Future<GoRouter> pumpLesson(WidgetTester tester, int gameId) async {
  tester.view.physicalSize = const Size(400, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final repo = sampleRepo()
    ..details[9] = const RulesLesson(
      gameId: 9,
      gameName: hostGameName,
      video: null,
      hasRulebook: true,
      suggestedQuestions: suggested,
    );
  final router = GoRouter(
    initialLocation: '/rules/$gameId',
    routes: [
      GoRoute(
        path: '/rules/:id',
        builder: (context, state) =>
            RulesLessonPage(gameId: int.parse(state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/host',
        builder: (context, state) => const Scaffold(body: Text('語音主持頁')),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        rulesQaRepositoryProvider.overrideWithValue(repo),
        lessonVideoPlayerProvider.overrideWithValue(
          const FakeLessonVideoPlayer(),
        ),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return router;
}

void main() {
  testWidgets('血與刃的白薔薇：有「開 AI 語音主持」，點了進語音主持頁', (tester) async {
    await pumpLesson(tester, 9);
    final entry = find.byKey(const Key('rules-host-entry'));
    expect(entry, findsOneWidget);
    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.text('語音主持頁'), findsOneWidget);
  });

  testWidgets('其他遊戲：沒有語音主持入口', (tester) async {
    await pumpLesson(tester, 1);
    expect(find.byKey(const Key('rules-host-entry')), findsNothing);
  });
}
