import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/core/dev/widgets/dev_user_switcher.dart';

import '../../support/fakes.dart';

Future<ProviderContainer> pumpSwitcher(
  WidgetTester tester, {
  bool dev = true,
  required FakeDevUsersRepository repo,
}) async {
  final container = ProviderContainer(
    overrides: [
      appConfigProvider.overrideWithValue(
        AppConfig(
          apiBaseUrl: 'http://api.test',
          showPrototypes: false,
          devUserEnabled: dev,
        ),
      ),
      devUsersRepositoryProvider.overrideWithValue(repo),
    ],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: Scaffold(body: DevUserSwitcher())),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

void main() {
  testWidgets('從 API 載入清單並可選取，選取後標頭身分改變', (tester) async {
    final repo = FakeDevUsersRepository();
    final container = await pumpSwitcher(tester, repo: repo);
    expect(repo.callCount, 1);
    expect(find.textContaining('測試玩家'), findsWidgets);

    await tester.tap(find.byType(DropdownButton<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('測試管理員').last);
    await tester.pumpAndSettle();

    expect(container.read(selectedDevUserIdProvider), 'u-admin');
    expect(container.read(devUserHeaderProvider), 'u-admin:admin');
  });

  testWidgets('載入失敗顯示錯誤與重試，重試後恢復', (tester) async {
    final repo = FakeDevUsersRepository(error: Exception('boom'));
    await pumpSwitcher(tester, repo: repo);
    expect(find.text('無法載入測試帳號'), findsOneWidget);

    repo.error = null;
    await tester.tap(find.text('重試'));
    await tester.pumpAndSettle();
    expect(find.text('無法載入測試帳號'), findsNothing);
    expect(find.byType(DropdownButton<String>), findsOneWidget);
    expect(repo.callCount, 2);
  });

  testWidgets('清單為空顯示 seed 提示', (tester) async {
    await pumpSwitcher(tester, repo: FakeDevUsersRepository(users: []));
    expect(find.textContaining('請先執行 seed'), findsOneWidget);
  });

  testWidgets('正式環境不顯示切換器，也不呼叫 API', (tester) async {
    final repo = FakeDevUsersRepository();
    await pumpSwitcher(tester, dev: false, repo: repo);
    expect(find.byType(DropdownButton<String>), findsNothing);
    expect(repo.callCount, 0);
  });
}
