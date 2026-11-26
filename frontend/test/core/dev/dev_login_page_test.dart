// 開發用登入畫面：選測試帳號 → 登入 → 設定目前身分 → 回首頁。不是真的認證。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/core/dev/widgets/dev_login_page.dart';

import '../../support/fakes.dart';

/// 從 `/login` 開始，`/` 是只顯示文字的假首頁。[settle] 為 false 時只推進一個畫格（看載入中）。
Future<ProviderContainer> pumpLogin(
  WidgetTester tester, {
  required FakeDevUsersRepository repo,
  bool settle = true,
}) async {
  final container = ProviderContainer(
    overrides: [
      appConfigProvider.overrideWithValue(
        const AppConfig(
          apiBaseUrl: 'http://api.test',
          showPrototypes: false,
          devUserEnabled: true,
        ),
      ),
      devUsersRepositoryProvider.overrideWithValue(repo),
    ],
  );
  addTearDown(container.dispose);
  final router = GoRouter(
    initialLocation: '/login',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) =>
            const Scaffold(body: Text('首頁', key: Key('fake-home'))),
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => const DevLoginPage(),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
  return container;
}

Finder submitButton() => find.byKey(const Key('dev-login-submit'));

bool submitEnabled(WidgetTester tester) =>
    tester.widget<ButtonStyleButton>(submitButton()).onPressed != null;

void main() {
  testWidgets('列出後端回傳的每個測試帳號（名稱與角色）', (tester) async {
    final repo = FakeDevUsersRepository();
    await pumpLogin(tester, repo: repo);
    expect(find.byKey(const Key('dev-login-page')), findsOneWidget);
    expect(repo.callCount, 1);
    // 數量依後端 seed 而定，不寫死
    for (final user in repo.users) {
      expect(find.text(user.displayName), findsOneWidget);
      expect(find.text(user.role), findsOneWidget);
    }
  });

  testWidgets('還沒選帳號時，「登入」不能按', (tester) async {
    await pumpLogin(tester, repo: FakeDevUsersRepository());
    expect(submitButton(), findsOneWidget);
    expect(submitEnabled(tester), isFalse);
  });

  testWidgets('選一個帳號按「登入」：身分切換、標頭改變、回到首頁', (tester) async {
    final container = await pumpLogin(tester, repo: FakeDevUsersRepository());
    await tester.tap(find.text('測試管理員'));
    await tester.pumpAndSettle();
    expect(submitEnabled(tester), isTrue);

    await tester.tap(submitButton());
    await tester.pumpAndSettle();

    expect(container.read(selectedDevUserIdProvider), 'u-admin');
    expect(container.read(devUserHeaderProvider), 'u-admin:admin');
    expect(find.byKey(const Key('fake-home')), findsOneWidget);
    expect(find.byKey(const Key('dev-login-page')), findsNothing);
  });

  testWidgets('清單還沒回來時顯示載入中', (tester) async {
    final repo = FakeDevUsersRepository()..gate = Completer<void>();
    await pumpLogin(tester, repo: repo, settle: false);
    expect(find.byKey(const Key('dev-login-loading')), findsOneWidget);
    expect(submitButton(), findsNothing);

    repo.gate!.complete();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dev-login-loading')), findsNothing);
  });

  testWidgets('載入失敗顯示錯誤與重試，重試後列出清單', (tester) async {
    final repo = FakeDevUsersRepository(error: Exception('boom'));
    await pumpLogin(tester, repo: repo);
    expect(find.byKey(const Key('dev-login-error')), findsOneWidget);
    expect(submitButton(), findsNothing);

    repo.error = null;
    await tester.tap(find.byKey(const Key('dev-login-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dev-login-error')), findsNothing);
    expect(find.text('測試玩家'), findsOneWidget);
    expect(repo.callCount, 2);
  });

  testWidgets('沒有測試帳號時提示先執行 seed', (tester) async {
    await pumpLogin(tester, repo: FakeDevUsersRepository(users: []));
    expect(find.textContaining('請先執行 seed'), findsOneWidget);
    expect(submitButton(), findsNothing);
  });
}
