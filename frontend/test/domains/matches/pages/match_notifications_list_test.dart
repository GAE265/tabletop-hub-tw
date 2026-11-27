// 戰績通知列表（通知頁的「戰績」分頁）：文字、點擊導頁、沒有通知、載入失敗
// （docs/mr_info/feature-matches-notifications.md 的前端情境表）。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/matches/pages/widgets/match_notifications_list.dart';
import 'package:tabletop_hub/domains/matches/state/match_current_user.dart';
import 'package:tabletop_hub/domains/matches/state/match_notifications_state.dart';

import '../../../support/fakes.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');
final nowUtc = DateTime.utc(2026, 11, 20, 4);

/// `/` 是戰績通知列表，`/matches/:id` 是假的一局頁面。
Future<GoRouter> pumpList(
  WidgetTester tester,
  FakeMatchesRepository repo,
) async {
  tester.view.physicalSize = const Size(400, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) =>
            const Scaffold(body: MatchNotificationsList()),
      ),
      GoRoute(
        path: '/matches/:id',
        builder: (context, state) => Scaffold(
          body: Center(child: Text('一局頁 ${state.pathParameters['id']}')),
        ),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        matchesRepositoryProvider.overrideWithValue(repo),
        matchUserIdProvider.overrideWithValue('u-b'),
        matchNotificationsClockProvider.overrideWithValue(() => nowUtc),
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

Finder card(String id) => find.byKey(Key('match-notification-$id'));

void main() {
  testWidgets('通知文字包含記錄者名稱', (tester) async {
    await pumpList(
      tester,
      FakeMatchesRepository()..notifications = [fakeMatchNotification()],
    );
    expect(
      find.descendant(
        of: card('mn-1'),
        matching: find.text('測試玩家 記錄了《血與刃的白薔薇》的結果，請確認'),
      ),
      findsOneWidget,
    );
    expect(matchNotificationText(fakeMatchNotification()), contains('測試玩家'));
  });

  testWidgets('點未讀的通知：標成已讀，前往這一局', (tester) async {
    final repo = FakeMatchesRepository()
      ..notifications = [fakeMatchNotification(matchId: 'm-7')];
    final router = await pumpList(tester, repo);
    expect(
      find.byKey(const Key('match-notification-unread-mn-1')),
      findsOneWidget,
    );
    await tester.tap(card('mn-1'));
    await tester.pumpAndSettle();
    expect(repo.markReadCalls, ['mn-1']);
    expect(router.state.uri.path, '/matches/m-7');
    expect(find.text('一局頁 m-7'), findsOneWidget);
  });

  testWidgets('點已讀的通知：不送出，直接前往', (tester) async {
    final repo = FakeMatchesRepository()
      ..notifications = [fakeMatchNotification(readAt: nowUtc)];
    final router = await pumpList(tester, repo);
    expect(
      find.byKey(const Key('match-notification-unread-mn-1')),
      findsNothing,
    );
    await tester.tap(card('mn-1'));
    await tester.pumpAndSettle();
    expect(repo.markReadCalls, isEmpty);
    expect(router.state.uri.path, '/matches/m-1');
  });

  testWidgets('標成已讀失敗：仍然前往，回來後維持未讀', (tester) async {
    final repo = FakeMatchesRepository()
      ..notifications = [fakeMatchNotification()]
      ..markReadError = failure;
    final router = await pumpList(tester, repo);
    await tester.tap(card('mn-1'));
    await tester.pumpAndSettle();
    expect(router.state.uri.path, '/matches/m-1');
    router.go('/');
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('match-notification-unread-mn-1')),
      findsOneWidget,
    );
  });

  testWidgets('沒有通知：「目前沒有戰績通知」', (tester) async {
    await pumpList(tester, FakeMatchesRepository());
    expect(find.text('目前沒有戰績通知'), findsOneWidget);
  });

  testWidgets('載入失敗：中文錯誤與重試；重試後顯示通知', (tester) async {
    final repo = FakeMatchesRepository()..notificationsError = failure;
    await pumpList(tester, repo);
    expect(find.text('伺服器忙碌中'), findsOneWidget);
    expect(find.textContaining('SERVER_ERROR'), findsNothing);
    repo
      ..notificationsError = null
      ..notifications = [fakeMatchNotification()];
    await tester.tap(find.text('重試'));
    await tester.pumpAndSettle();
    expect(card('mn-1'), findsOneWidget);
  });
}
