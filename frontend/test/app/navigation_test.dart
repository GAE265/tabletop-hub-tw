// 主要導覽列（spec：frontend-shell 的「主要導覽列」）。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/navigation.dart';
import 'package:tabletop_hub/app/shell.dart';
import 'package:tabletop_hub/app/theme/app_colors.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';

import '../support/fakes.dart';

const navKeys = [
  'shell-nav-home',
  'shell-nav-groups',
  'shell-nav-advisor',
  'shell-nav-rules',
  'shell-nav-booking',
  'shell-nav-matches',
];

/// 以框架包住只顯示路徑的假頁面，從 [location] 開始。
Future<GoRouter> pumpShell(
  WidgetTester tester, {
  String location = '/',
  Size size = const Size(400, 900),
  DevUser? user,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  Widget page(GoRouterState state) =>
      Scaffold(body: Center(child: Text('頁面 ${state.uri.path}')));
  final router = GoRouter(
    initialLocation: location,
    routes: [
      ShellRoute(
        builder: (context, state, child) =>
            AppShell(location: state.uri.path, child: child),
        routes: [
          for (final path in [
            '/',
            '/matches',
            '/matches/m-1',
            '/groups',
            '/notifications',
            '/rules-ingest',
            '/videos',
            '/videos/p1/draft',
            '/videos/p1/assets',
            '/games-advisor',
            '/rules',
            '/rules/1',
            '/booking',
            '/booking/mine',
            '/health',
            '/proto/theme',
          ])
            GoRoute(path: path, builder: (context, state) => page(state)),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        // 指定目前身分（add-rules-ingest-page：管理員才有「匯入」）
        if (user != null) currentDevUserProvider.overrideWithValue(user),
        // 鈴鐺查詢揪團與訂位的未讀數，用假的 repository
        // （add-groups-notifications、add-booking-notifications）
        groupsRepositoryProvider.overrideWithValue(FakeGroupsRepository()),
        bookingRepositoryProvider.overrideWithValue(FakeBookingRepository()),
        appConfigProvider.overrideWithValue(
          const AppConfig(
            apiBaseUrl: 'http://api.test',
            showPrototypes: false,
            devUserEnabled: false,
          ),
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

/// 品牌 logo 圖片（橫式完整版：魚＋遊任有娛＋PLAY · GAME · FUN）。
final logoImage = find.byWidgetPredicate(
  (widget) =>
      widget is Image &&
      widget.image is AssetImage &&
      (widget.image as AssetImage).assetName == BrandMark.asset,
);

/// 每個導覽項目的 Key 掛在它的 [Semantics] 上，選取狀態也由 Semantics 對外表達。
bool isSelected(WidgetTester tester, String key) =>
    tester.widget<Semantics>(find.byKey(Key(key))).properties.selected ?? false;

void main() {
  group('選取規則', () {
    test('首頁只在路徑剛好是 / 時選取', () {
      expect(selectedNavPath('/'), '/');
      expect(selectedNavPath('/groups'), '/groups');
    });

    test('子路徑選取所屬項目', () {
      expect(selectedNavPath('/booking/mine'), '/booking');
      expect(selectedNavPath('/booking/board'), '/booking');
      expect(selectedNavPath('/rules/1'), '/rules');
      expect(selectedNavPath('/matches/m-1'), '/matches');
    });

    test('不屬於任何項目：沒有選取', () {
      expect(selectedNavPath('/health'), isNull);
      expect(selectedNavPath('/proto/theme'), isNull);
      expect(selectedNavPath('/bookings'), isNull);
    });

    test('項目依序為首頁、揪團、推薦、規則、訂位、戰績', () {
      expect(navItems.map((item) => item.label), [
        '首頁',
        '揪團',
        '推薦',
        '規則',
        '訂位',
        '戰績',
      ]);
      expect(navItems.map((item) => item.path), [
        '/',
        '/groups',
        '/games-advisor',
        '/rules',
        '/booking',
        '/matches',
      ]);
    });
  });

  testWidgets('手機：導覽列在畫面底部，六個項目都有圖示與文字', (tester) async {
    await pumpShell(tester, size: const Size(400, 900));
    for (final key in navKeys) {
      final item = find.byKey(Key(key));
      expect(item, findsOneWidget);
      expect(tester.getTopLeft(item).dy, greaterThan(800));
      expect(
        find.descendant(of: item, matching: find.byType(Icon)),
        findsOneWidget,
      );
    }
    expect(
      find.descendant(
        of: find.byKey(const Key('shell-nav-rules')),
        matching: find.text('規則'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('桌機：導覽列在畫面頂部', (tester) async {
    await pumpShell(tester, size: const Size(1280, 900));
    final page = tester.getTopLeft(find.text('頁面 /'));
    for (final key in navKeys) {
      expect(tester.getTopLeft(find.byKey(Key(key))).dy, lessThan(page.dy));
    }
  });

  testWidgets('在 /booking/mine：「訂位」為選取狀態，其他不是', (tester) async {
    await pumpShell(tester, location: '/booking/mine');
    expect(isSelected(tester, 'shell-nav-booking'), isTrue);
    for (final key in navKeys.where((k) => k != 'shell-nav-booking')) {
      expect(isSelected(tester, key), isFalse, reason: key);
    }
  });

  testWidgets('在 /groups：「揪團」選取，「首頁」沒有選取（桌機）', (tester) async {
    await pumpShell(tester, location: '/groups', size: const Size(1280, 900));
    expect(isSelected(tester, 'shell-nav-groups'), isTrue);
    expect(isSelected(tester, 'shell-nav-home'), isFalse);
  });

  testWidgets('點「規則」前往 /rules', (tester) async {
    await pumpShell(tester);
    await tester.tap(find.byKey(const Key('shell-nav-rules')));
    await tester.pumpAndSettle();
    expect(find.text('頁面 /rules'), findsOneWidget);
    expect(isSelected(tester, 'shell-nav-rules'), isTrue);
  });

  testWidgets('在 /health：導覽列照常顯示，沒有項目選取', (tester) async {
    await pumpShell(tester, location: '/health');
    for (final key in navKeys) {
      expect(find.byKey(Key(key)), findsOneWidget);
      expect(isSelected(tester, key), isFalse, reason: key);
    }
  });

  testWidgets('每個導覽項目只出現一次（手機與桌機）', (tester) async {
    for (final size in const [Size(400, 900), Size(1280, 900)]) {
      await pumpShell(tester, size: size);
      for (final key in navKeys) {
        expect(find.byKey(Key(key)), findsOneWidget, reason: '$key $size');
      }
    }
  });

  testWidgets('在 /matches/m-1：「戰績」為選取狀態', (tester) async {
    await pumpShell(tester, location: '/matches/m-1');
    expect(isSelected(tester, 'shell-nav-matches'), isTrue);
    expect(isSelected(tester, 'shell-nav-home'), isFalse);
  });

  group('Stitch 版面（手機）', () {
    testWidgets('頂部列：品牌 logo（讀屏唸「遊任有娛」）、鈴鐺與登入', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final bar = find.byType(MobileTopBar);
      Finder inBar(Finder f) => find.descendant(of: bar, matching: f);
      expect(inBar(logoImage), findsOneWidget);
      expect(tester.widget<Image>(inBar(logoImage)).semanticLabel, '遊任有娛');
      expect(
        inBar(find.byKey(const Key('shell-notification-bell'))),
        findsOneWidget,
      );
      expect(inBar(find.byKey(const Key('shell-login'))), findsOneWidget);
    });

    testWidgets('頂部列的登入：提示「登入功能即將推出」', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      await tester.tap(find.byKey(const Key('shell-login')));
      await tester.pump();
      expect(find.text('登入功能即將推出'), findsOneWidget);
    });

    testWidgets('頂部列：白色滿版，底部有較粗的邊與陰影；logo 高 60', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final bar = find.byType(MobileTopBar);
      final decoration =
          tester
                  .widget<DecoratedBox>(
                    find
                        .descendant(
                          of: bar,
                          matching: find.byType(DecoratedBox),
                        )
                        .first,
                  )
                  .decoration
              as BoxDecoration;
      expect(decoration.color, AppColors.surface);
      final border = decoration.border! as Border;
      expect(border.bottom.width, greaterThan(border.top.width));
      expect(decoration.boxShadow, isNotEmpty);
      expect(
        tester.getSize(find.descendant(of: bar, matching: logoImage)).height,
        60,
      );
    });

    testWidgets('頂部列：鈴鐺與登入一樣大，右邊留白和左邊一樣 16', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final bell = find.byKey(const Key('shell-notification-bell'));
      final login = find.byKey(const Key('shell-login'));
      expect(tester.getSize(bell), tester.getSize(login));
      expect(tester.getTopRight(login).dx, 400 - 16);
      final logo = find.descendant(
        of: find.byType(MobileTopBar),
        matching: logoImage,
      );
      expect(tester.getTopLeft(logo).dx, 16);
    });

    testWidgets('頂部列：鈴鐺與登入的底色、圖示顏色一樣（白底深色圖示）', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      Color? fill(String key) =>
          (tester
                      .widget<DecoratedBox>(
                        find
                            .descendant(
                              of: find.byKey(Key(key)),
                              matching: find.byType(DecoratedBox),
                            )
                            .first,
                      )
                      .decoration
                  as BoxDecoration)
              .color;
      Color? iconColor(String key) => tester
          .widget<Icon>(
            find
                .descendant(
                  of: find.byKey(Key(key)),
                  matching: find.byType(Icon),
                )
                .first,
          )
          .color;
      for (final key in ['shell-notification-bell', 'shell-login']) {
        expect(fill(key), AppColors.surface, reason: key);
        expect(iconColor(key), AppColors.ink, reason: key);
      }
    });

    for (final key in ['shell-notification-bell', 'shell-login']) {
      testWidgets('按住頂部列的「$key」：底邊變薄、往下沉，移開後彈回', (tester) async {
        await pumpShell(tester, size: const Size(400, 900));
        final button = find.byKey(Key(key));
        final frame = find
            .descendant(of: button, matching: find.byType(DecoratedBox))
            .first;
        double edge() =>
            ((tester.widget<DecoratedBox>(frame).decoration as BoxDecoration)
                        .border!
                    as Border)
                .bottom
                .width;
        final icon = find
            .descendant(of: button, matching: find.byType(Icon))
            .first;
        final restEdge = edge();
        final restTop = tester.getTopLeft(icon).dy;
        final gesture = await tester.startGesture(tester.getCenter(button));
        await tester.pumpAndSettle();
        expect(edge(), lessThan(restEdge));
        expect(tester.getTopLeft(icon).dy, greaterThan(restTop));
        await gesture.cancel();
        await tester.pumpAndSettle();
        expect(edge(), restEdge);
        expect(tester.getTopLeft(icon).dy, restTop);
      });
    }

    testWidgets('頂部列與底部導覽列放在木紋上', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final wood = find.byType(WoodBackground);
      expect(wood, findsOneWidget);
      for (final type in [MobileTopBar, BottomNavigation]) {
        expect(
          find.descendant(of: wood, matching: find.byType(type)),
          findsOneWidget,
        );
      }
    });

    for (final location in [
      '/',
      '/groups',
      '/matches',
      '/matches/m-1',
      '/videos/p1/assets',
      '/videos',
      '/videos/p1/draft',
    ]) {
      testWidgets('$location：內容延伸到導覽列後面，並告訴頁面底部要留多少空間', (tester) async {
        await pumpShell(tester, location: location, size: const Size(400, 900));
        final page = find.byType(Scaffold).last;
        expect(tester.getBottomLeft(page).dy, 900);
        final nav = tester.getTopLeft(find.byType(BottomNavigation)).dy;
        final padding = MediaQuery.paddingOf(tester.element(page)).bottom;
        expect(padding, greaterThanOrEqualTo(900 - nav));
      });
    }

    testWidgets('其他頁面：內容停在導覽列上方', (tester) async {
      // 揪團、訂位、戰績頁都改成浮動導覽列，這裡改用不會改版的規則書入庫頁
      await pumpShell(
        tester,
        location: '/rules-ingest',
        size: const Size(400, 900),
      );
      final page = find.byType(Scaffold).last;
      final nav = tester.getTopLeft(find.byType(BottomNavigation)).dy;
      expect(tester.getBottomLeft(page).dy, lessThanOrEqualTo(nav));
    });

    testWidgets('頁面要求藏起導覽列（語音主持中）：手機沒有底部導覽列，內容延伸到底；取消後恢復', (tester) async {
      await pumpShell(tester, location: '/', size: const Size(400, 900));
      final container = ProviderScope.containerOf(
        tester.element(find.byType(AppShell)),
      );
      container.read(hideBottomNavigationProvider.notifier).set(true);
      await tester.pumpAndSettle();
      expect(find.byType(BottomNavigation), findsNothing);
      expect(tester.getBottomLeft(find.byType(Scaffold).last).dy, 900);

      container.read(hideBottomNavigationProvider.notifier).set(false);
      await tester.pumpAndSettle();
      expect(find.byType(BottomNavigation), findsOneWidget);
    });

    testWidgets('桌機：沒有木紋框（版面不變）', (tester) async {
      await pumpShell(tester, size: const Size(1280, 900));
      expect(find.byType(WoodBackground), findsNothing);
    });

    testWidgets('底部導覽列：選取的項目是深色底，其他是透明', (tester) async {
      await pumpShell(tester, location: '/groups', size: const Size(400, 900));
      Color? fill(String key) => tester
          .widget<Material>(
            find
                .descendant(
                  of: find.byKey(Key(key)),
                  matching: find.byType(Material),
                )
                .first,
          )
          .color;
      expect(fill('shell-nav-groups'), AppColors.ink);
      expect(fill('shell-nav-home'), Colors.transparent);
    });
  });

  testWidgets('桌機：頂部導覽列左邊是品牌 logo', (tester) async {
    await pumpShell(tester, size: const Size(1280, 900));
    expect(
      find.descendant(of: find.byType(TopNavigation), matching: logoImage),
      findsOneWidget,
    );
  });

  group('通知鈴鐺（add-groups-notifications）', () {
    testWidgets('手機：鈴鐺在畫面頂部', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final bell = find.byKey(const Key('shell-notification-bell'));
      expect(bell, findsOneWidget);
      expect(tester.getTopLeft(bell).dy, lessThan(100));
    });

    testWidgets('桌機：鈴鐺在頂部導覽列', (tester) async {
      await pumpShell(tester, size: const Size(1280, 800));
      final bell = find.byKey(const Key('shell-notification-bell'));
      expect(bell, findsOneWidget);
      expect(
        find.descendant(of: find.byType(TopNavigation), matching: bell),
        findsOneWidget,
      );
    });

    // add-booking-notifications：通知頁改成 /notifications，同時有揪團與訂位，
    // 不屬於任何導覽項目
    testWidgets('點鈴鐺：前往通知頁，導覽列不選取任何項目', (tester) async {
      final router = await pumpShell(tester, size: const Size(1280, 800));
      await tester.tap(find.byKey(const Key('shell-notification-bell')));
      await tester.pumpAndSettle();
      expect(router.state.uri.path, '/notifications');
      for (final key in navKeys) {
        expect(isSelected(tester, key), isFalse, reason: key);
      }
    });
  });

  group('管理員才有的「匯入」（add-rules-ingest-page）', () {
    const admin = DevUser(id: 'u-admin', displayName: '測試管理員', role: 'admin');
    const player = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');
    const staff = DevUser(
      id: 'u-staff',
      displayName: '測試店家人員',
      role: 'shop_staff',
      shopId: 's-b',
    );
    const key = Key('shell-nav-rules-ingest');

    for (final size in [const Size(400, 900), const Size(1280, 800)]) {
      testWidgets('管理員（寬度 ${size.width.toInt()}）：有「匯入」，點下前往 /rules-ingest', (
        tester,
      ) async {
        final router = await pumpShell(tester, size: size, user: admin);
        expect(find.byKey(key), findsOneWidget);
        await tester.tap(find.byKey(key));
        await tester.pumpAndSettle();
        expect(router.state.uri.path, '/rules-ingest');
        expect(isSelected(tester, 'shell-nav-rules-ingest'), isTrue);
        for (final other in navKeys) {
          expect(isSelected(tester, other), isFalse, reason: other);
        }
      });
    }

    for (final user in [player, staff, null]) {
      testWidgets('${user?.role ?? '沒有身分'}：沒有「匯入」，其他項目不變', (tester) async {
        await pumpShell(tester, user: user);
        expect(find.byKey(key), findsNothing);
        for (final other in navKeys) {
          expect(find.byKey(Key(other)), findsOneWidget, reason: other);
        }
      });
    }
  });
  group('店家人員與管理員才有的「影片」（add-rules-video-mobile）', () {
    const key = Key('shell-nav-videos');

    test('「影片」放在「規則」後面', () {
      expect(visibleNavItems('shop_staff').map((item) => item.label), [
        '首頁',
        '揪團',
        '推薦',
        '規則',
        '影片',
        '訂位',
        '戰績',
      ]);
      expect(visibleNavItems('admin').map((item) => item.label), [
        '首頁',
        '揪團',
        '推薦',
        '規則',
        '影片',
        '訂位',
        '戰績',
        '匯入',
      ]);
      expect(
        visibleNavItems(
          'shop_staff',
        ).firstWhere((item) => item.path == '/videos').icon,
        Icons.video_library_outlined,
      );
    });

    test('子路徑選取「影片」', () {
      expect(selectedNavPath('/videos'), '/videos');
      expect(selectedNavPath('/videos/p1/draft'), '/videos');
    });

    for (final user in [fakeStaff, fakeAdmin]) {
      for (final size in [const Size(400, 900), const Size(1280, 800)]) {
        testWidgets(
          '${user.role}（寬度 ${size.width.toInt()}）：有「影片」，點下前往 /videos',
          (tester) async {
            final router = await pumpShell(tester, size: size, user: user);
            expect(find.byKey(key), findsOneWidget);
            await tester.tap(find.byKey(key));
            await tester.pumpAndSettle();
            expect(router.state.uri.path, '/videos');
            expect(isSelected(tester, 'shell-nav-videos'), isTrue);
          },
        );
      }
    }

    for (final user in [fakePlayer, null]) {
      testWidgets('${user?.role ?? '沒有身分'}：沒有「影片」', (tester) async {
        await pumpShell(tester, user: user);
        expect(find.byKey(key), findsNothing);
      });
    }

    testWidgets('在 /videos/p1/draft：「影片」為選取狀態', (tester) async {
      await pumpShell(tester, location: '/videos/p1/draft', user: fakeStaff);
      expect(isSelected(tester, 'shell-nav-videos'), isTrue);
      expect(isSelected(tester, 'shell-nav-rules'), isFalse);
    });
  });
}
