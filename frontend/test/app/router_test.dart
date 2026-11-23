import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/app.dart';
import 'package:tabletop_hub/app/theme/app_fonts.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/platform/lesson_video_player.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';

import '../support/fakes.dart';

Future<void> pumpApp(
  WidgetTester tester, {
  required bool showPrototypes,
  bool dev = false,
  DevUser? user,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        // 指定目前身分（add-rules-ingest-page：只有管理員能用的頁面）
        if (user != null) currentDevUserProvider.overrideWithValue(user),
        appConfigProvider.overrideWithValue(
          AppConfig(
            apiBaseUrl: 'http://api.test',
            showPrototypes: showPrototypes,
            devUserEnabled: dev,
          ),
        ),
        appFontsProvider.overrideWithValue(const FakeAppFonts()),
        devUsersRepositoryProvider.overrideWithValue(FakeDevUsersRepository()),
        groupsRepositoryProvider.overrideWithValue(FakeGroupsRepository()),
        bookingRepositoryProvider.overrideWithValue(FakeBookingRepository()),
        matchesRepositoryProvider.overrideWithValue(FakeMatchesRepository()),
        healthRepositoryProvider.overrideWithValue(
          FakeHealthRepository(
            result: const HealthStatus(status: 'ok', database: 'up'),
          ),
        ),
        advisorRepositoryProvider.overrideWithValue(FakeAdvisorRepository()),
        rulesQaRepositoryProvider.overrideWithValue(FakeRulesQaRepository()),
        videoStudioRepositoryProvider.overrideWithValue(
          FakeVideoStudioRepository(),
        ),
        lessonVideoPlayerProvider.overrideWithValue(
          const FakeLessonVideoPlayer(),
        ),
      ],
      child: const App(),
    ),
  );
  await tester.pumpAndSettle();
}

void goTo(WidgetTester tester, String location) {
  GoRouter.of(tester.element(find.byType(Scaffold).first)).go(location);
}

void main() {
  testWidgets('health 已有正式頁面，移除 /proto/health（SHOW_PROTOTYPES 開啟也找不到）', (
    tester,
  ) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/health');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('/games-advisor 是正式推薦頁（SHOW_PROTOTYPES 關閉也能使用）', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/games-advisor');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('games-advisor-page')), findsOneWidget);
  });

  testWidgets('正式頁面完成後移除 /proto/games_advisor（SHOW_PROTOTYPES 開啟也找不到）', (
    tester,
  ) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/games_advisor');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('SHOW_PROTOTYPES 開啟：/proto/theme 顯示主題預覽', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/theme');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('theme-preview-page')), findsOneWidget);
  });

  testWidgets('SHOW_PROTOTYPES 關閉：/proto/theme 顯示找不到頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/proto/theme');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('theme-preview-page')), findsNothing);
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  // add-home-page：`/` 從 health 頁面改成首頁，health 頁面移到 `/health`。
  testWidgets('訂位、我的訂位、店家看板之間切換沒有換頁動畫', (tester) async {
    tester.view.physicalSize = const Size(400, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/booking');
    await tester.pumpAndSettle();
    goTo(tester, '/booking/mine');
    // 只推進一個畫格：沒有動畫的話，新頁面已經在原位
    await tester.pump();
    await tester.pump();
    expect(tester.getTopLeft(find.byKey(const Key('my-bookings-page'))).dx, 0);
    expect(find.byKey(const Key('booking-page')), findsNothing);
  });

  testWidgets('/ 是首頁', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    expect(find.byKey(const Key('home-page')), findsOneWidget);
    expect(find.byKey(const Key('health-page')), findsNothing);
  });

  testWidgets('/health 是套主題的正式 health 頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/health');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('health-page')), findsOneWidget);
    expect(find.textContaining('ok'), findsWidgets);
  });

  testWidgets('開發環境框架顯示身分切換器', (tester) async {
    await pumpApp(tester, showPrototypes: false, dev: true);
    expect(find.byType(DropdownButton<String>), findsOneWidget);
  });

  testWidgets('正式環境框架沒有身分切換器', (tester) async {
    await pumpApp(tester, showPrototypes: false, dev: false);
    expect(find.byType(DropdownButton<String>), findsNothing);
  });

  testWidgets('/groups 是正式揪團月曆（SHOW_PROTOTYPES 關閉也能使用）', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/groups');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('groups-page')), findsOneWidget);
  });

  // add-booking-notifications：通知頁從 /groups/notifications 改成 /notifications
  testWidgets('/groups/{id} 是揪團詳細頁，/notifications 是通知頁', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/groups/g-1');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    goTo(tester, '/notifications');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('notifications-page')), findsOneWidget);
    expect(find.byKey(const Key('group-detail-page')), findsNothing);
  });

  testWidgets('正式頁面完成後移除 /proto/groups（SHOW_PROTOTYPES 開啟也找不到）', (
    tester,
  ) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/groups');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('畫面框架的「揪團」入口進到 /groups', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    await tester.tap(find.byKey(const Key('shell-nav-groups')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('groups-page')), findsOneWidget);
  });

  testWidgets('畫面框架的「推薦」入口進到 /games-advisor', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    await tester.tap(find.byKey(const Key('shell-nav-advisor')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('games-advisor-page')), findsOneWidget);
  });

  testWidgets('/rules 是正式規則教學頁（SHOW_PROTOTYPES 關閉也能使用）', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/rules');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules-lessons-page')), findsOneWidget);
  });

  testWidgets('/rules/{game_id} 是某款遊戲的教學頁', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/rules/2');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules-lesson-page')), findsOneWidget);
  });

  testWidgets('正式頁面完成後移除 /proto/rules_qa（SHOW_PROTOTYPES 開啟也找不到）', (
    tester,
  ) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/rules_qa');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('畫面框架的「規則」入口進到 /rules', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    await tester.tap(find.byKey(const Key('shell-nav-rules')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rules-lessons-page')), findsOneWidget);
  });

  testWidgets('/matches 是正式戰績頁，/matches/{id} 是一局', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/matches');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matches-page')), findsOneWidget);
    goTo(tester, '/matches/m-1');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('match-detail-page')), findsOneWidget);
  });

  testWidgets('正式頁面完成後移除 /proto/matches（SHOW_PROTOTYPES 開啟也找不到）', (
    tester,
  ) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/matches');
    await tester.pumpAndSettle();
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('畫面框架的「戰績」入口進到 /matches', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    await tester.tap(find.byKey(const Key('shell-nav-matches')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matches-page')), findsOneWidget);
  });
  testWidgets('店家人員從「影片」入口進到影片專案列表（add-rules-video-mobile）', (tester) async {
    await pumpApp(tester, showPrototypes: false, user: fakeStaff);
    await tester.tap(find.byKey(const Key('shell-nav-videos')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('video-projects-page')), findsOneWidget);
  });
}
