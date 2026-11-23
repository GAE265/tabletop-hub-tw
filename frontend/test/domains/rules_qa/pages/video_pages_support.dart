// 規則影片手機頁的測試共用工具（MR 6 起）：用 go_router 打開 /videos 底下的頁面。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/core/platform/video_file_player.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/video_routes.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';

import '../../../support/fakes.dart';

class Harness {
  Harness(this.repo, this.router);

  final FakeVideoStudioRepository repo;
  final GoRouter router;

  String get path => router.state.uri.toString();
}

Future<Harness> pumpVideo(
  WidgetTester tester, {
  required String location,
  FakeVideoStudioRepository? repo,
  DevUser? user = fakeStaff,
  Size size = const Size(400, 900),
  Duration pollInterval = Duration.zero,
  bool settle = true,
  FakeImagePicker? picker,
  FakeVideoFilePlayer? player,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = repo ?? FakeVideoStudioRepository();
  final router = GoRouter(
    initialLocation: location,
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const Scaffold(body: Text('首頁')),
      ),
      videoStudioRoute,
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        videoStudioRepositoryProvider.overrideWithValue(fake),
        videoJobPollIntervalProvider.overrideWithValue(pollInterval),
        currentDevUserProvider.overrideWithValue(user),
        imagePickerProvider.overrideWithValue(picker ?? FakeImagePicker()),
        videoFilePlayerProvider.overrideWithValue(
          player ?? FakeVideoFilePlayer(),
        ),
      ],
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
    await tester.pump();
  }
  return Harness(fake, router);
}

/// 工作一直在進行的測試：拆掉畫面後讓排定的查詢跑完，查詢迴圈發現已拆掉就結束。
Future<void> stopPolling(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump(const Duration(seconds: 1));
}

Future<void> tapText(WidgetTester tester, String text) async {
  final target = find.text(text);
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}
