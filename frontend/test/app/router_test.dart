import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/app.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';

import '../support/fakes.dart';

Future<void> pumpApp(
  WidgetTester tester, {
  required bool showPrototypes,
  bool dev = false,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(
          AppConfig(
            apiBaseUrl: 'http://api.test',
            showPrototypes: showPrototypes,
            devUserEnabled: dev,
          ),
        ),
        devUsersRepositoryProvider.overrideWithValue(FakeDevUsersRepository()),
        healthRepositoryProvider.overrideWithValue(
          FakeHealthRepository(
            result: const HealthStatus(status: 'ok', database: 'up'),
          ),
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
  testWidgets('SHOW_PROTOTYPES 開啟：/proto/health 顯示參考畫面', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/health');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('health-proto-page')), findsOneWidget);
  });

  testWidgets('SHOW_PROTOTYPES 關閉：/proto/health 顯示找不到頁面', (tester) async {
    await pumpApp(tester, showPrototypes: false);
    goTo(tester, '/proto/health');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('health-proto-page')), findsNothing);
    expect(find.text('找不到頁面'), findsOneWidget);
  });

  testWidgets('首頁是套主題的正式 health 頁面', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    expect(find.byKey(const Key('health-page')), findsOneWidget);
    expect(find.textContaining('ok'), findsWidgets);
  });

  testWidgets('參考畫面與正式頁面共用同一個 state（同一份資料）', (tester) async {
    await pumpApp(tester, showPrototypes: true);
    goTo(tester, '/proto/health');
    await tester.pumpAndSettle();
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
}
