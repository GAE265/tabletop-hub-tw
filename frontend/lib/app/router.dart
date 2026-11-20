import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/config/app_config.dart';
import '../domains/booking/pages/new_booking_page.dart';
import '../domains/booking/pages/my_bookings_page.dart';
import '../domains/booking/pages/shop_board_page.dart';
import '../domains/games_advisor/pages/games_advisor_page.dart';
import '../domains/groups/pages/group_detail_page.dart';
import '../domains/groups/pages/groups_page.dart';
import '../domains/health/pages/health_page.dart';
import '../domains/matches/pages/match_detail_page.dart';
import '../domains/matches/pages/matches_page.dart';
import '../domains/rules_qa/pages/rules_lesson_page.dart';
import '../domains/rules_qa/pages/rules_lessons_page.dart';
import '../prototypes/booking/booking_list_proto_page.dart';
import '../prototypes/booking/booking_proto_page.dart';
import '../prototypes/rules_ingest/rules_ingest_proto_page.dart';
import 'home/pages/home_page.dart';
import 'notifications/notifications_page.dart';
import 'shell.dart';
import 'theme/theme_preview_page.dart';

/// 路由表。`/proto/...` 只有在 `SHOW_PROTOTYPES=true` 時才註冊，正式部署看不到。
GoRouter createRouter(AppConfig config) => GoRouter(
  routes: [
    ShellRoute(
      builder: (context, state, child) =>
          AppShell(location: state.uri.path, child: child),
      routes: [
        GoRoute(path: '/', builder: (context, state) => const HomePage()),
        // 健康檢查只供開發使用，不放進導覽列
        GoRoute(
          path: '/health',
          builder: (context, state) => const HealthPage(),
        ),
        GoRoute(
          path: '/groups',
          builder: (context, state) => const GroupsPage(),
          routes: [
            GoRoute(
              path: ':id',
              builder: (context, state) =>
                  GroupDetailPage(groupId: state.pathParameters['id']!),
            ),
          ],
        ),
        // 揪團與訂位的通知（add-booking-notifications）
        GoRoute(
          path: '/notifications',
          builder: (context, state) => const NotificationsPage(),
        ),
        GoRoute(
          path: '/games-advisor',
          builder: (context, state) => const GamesAdvisorPage(),
        ),
        GoRoute(
          path: '/matches',
          builder: (context, state) =>
              MatchesPage.fromQuery(state.uri.queryParameters),
          routes: [
            GoRoute(
              path: ':id',
              builder: (context, state) =>
                  MatchDetailPage(matchId: state.pathParameters['id']!),
            ),
          ],
        ),
        GoRoute(
          path: '/booking',
          builder: (context, state) =>
              NewBookingPage.fromQuery(state.uri.queryParameters),
          routes: [
            GoRoute(
              path: 'mine',
              builder: (context, state) => const MyBookingsPage(),
            ),
            GoRoute(
              path: 'board',
              builder: (context, state) => const ShopBoardPage(),
            ),
          ],
        ),
        GoRoute(
          path: '/rules',
          builder: (context, state) => const RulesLessonsPage(),
          routes: [
            GoRoute(
              path: ':gameId',
              builder: (context, state) {
                final gameId = int.tryParse(state.pathParameters['gameId']!);
                return gameId == null
                    ? const Scaffold(body: Center(child: Text('找不到頁面')))
                    : RulesLessonPage(gameId: gameId);
              },
            ),
          ],
        ),
        if (config.showPrototypes) ...[
          GoRoute(
            path: '/proto/theme',
            builder: (context, state) => const ThemePreviewPage(),
          ),
          GoRoute(
            path: '/proto/rules-ingest',
            builder: (context, state) => const RulesIngestProtoPage(),
          ),
          GoRoute(
            path: '/proto/booking',
            builder: (context, state) => const BookingProtoPage(),
          ),
          GoRoute(
            path: '/proto/booking/list',
            builder: (context, state) => const BookingListProtoPage(),
          ),
        ],
      ],
    ),
  ],
  errorBuilder: (context, state) =>
      const Scaffold(body: Center(child: Text('找不到頁面'))),
);

final routerProvider = Provider<GoRouter>((ref) {
  final router = createRouter(ref.watch(appConfigProvider));
  ref.onDispose(router.dispose);
  return router;
});
