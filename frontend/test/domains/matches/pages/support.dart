import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/matches/pages/match_detail_page.dart';
import 'package:tabletop_hub/domains/matches/pages/matches_page.dart';
import 'package:tabletop_hub/domains/matches/state/match_current_user.dart';

import '../../../support/fakes.dart';

/// 以正式主題與路由開啟戰績頁面，從 [location] 開始。
Future<FakeMatchesRepository> pumpMatches(
  WidgetTester tester,
  String location, {
  FakeMatchesRepository? repo,
  FakeBookingRepository? booking,
  FakeGroupsRepository? groups,
  String? userId = 'u-player',
  Size size = const Size(400, 900),
  bool settle = true,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = repo ?? FakeMatchesRepository();
  final router = GoRouter(
    initialLocation: location,
    routes: [
      GoRoute(
        path: '/matches',
        builder: (context, state) => const MatchesPage(),
        routes: [
          GoRoute(
            path: ':id',
            builder: (context, state) =>
                MatchDetailPage(matchId: state.pathParameters['id']!),
          ),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        matchesRepositoryProvider.overrideWithValue(fake),
        bookingRepositoryProvider.overrideWithValue(
          booking ?? FakeBookingRepository(),
        ),
        groupsRepositoryProvider.overrideWithValue(
          groups ?? FakeGroupsRepository(),
        ),
        matchUserIdProvider.overrideWithValue(userId),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
  return fake;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  // 列表是延遲建立的：還沒建立的元件要先捲過去
  if (target.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      target,
      300,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

/// 從下拉選單選一個選項。
Future<void> choose(WidgetTester tester, String key, String option) async {
  await tapKey(tester, key);
  await tester.tap(find.text(option).last);
  await tester.pumpAndSettle();
}

Finder inKey(String key, Finder finder) =>
    find.descendant(of: find.byKey(Key(key)), matching: finder);
