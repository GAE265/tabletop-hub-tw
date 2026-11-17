import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/current_user.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../../support/fakes.dart';
import '../support.dart';

/// 把測試視窗設成指定大小（邏輯像素），測試結束後還原。
void setScreenSize(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

/// 以正式主題包住 [home]，換成假的 repository、固定時鐘與目前使用者。
Future<void> pumpGroupsWidget(
  WidgetTester tester,
  Widget home, {
  required FakeGroupsRepository repo,
  String? userId = 'u-player',
  Size size = const Size(400, 900),
  bool settle = true,
}) async {
  setScreenSize(tester, size);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        groupsRepositoryProvider.overrideWithValue(repo),
        groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
        currentUserIdProvider.overrideWithValue(userId),
      ],
      child: MaterialApp(
        theme: buildAppTheme(const FakeAppFonts()),
        home: home,
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
}
