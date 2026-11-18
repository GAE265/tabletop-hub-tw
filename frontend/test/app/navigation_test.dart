// 主要導覽列（spec：frontend-shell 的「主要導覽列」）。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/navigation.dart';
import 'package:tabletop_hub/app/shell.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/config/app_config.dart';

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
}
