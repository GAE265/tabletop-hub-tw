// 專案總覽的「刪除專案」（2026-11-24 永傑決定，最小版）：先確認，寫明刪除後無法復原、
// 成品影片也會一起刪除；刪除後回到專案列表；正在產生時顯示後端的說明並留在原頁。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';

import '../../../support/fakes.dart';
import 'video_pages_support.dart';

FakeVideoStudioRepository twoProjects() => FakeVideoStudioRepository(
  projects: [
    sampleVideoProject(),
    sampleVideoProject(id: 'p2', gameName: '另一款'),
  ],
);

void main() {
  testWidgets('專案總覽有「刪除專案」按鈕', (tester) async {
    await pumpVideo(tester, location: '/videos/p1', repo: twoProjects());
    expect(find.byKey(const Key('video-project-delete')), findsOneWidget);
  });

  testWidgets('按下後先確認：寫明刪除後無法復原、成品影片也會一起刪除', (tester) async {
    final repo = twoProjects();
    await pumpVideo(tester, location: '/videos/p1', repo: repo);
    await tapKey(tester, 'video-project-delete');
    expect(find.textContaining('刪除後無法復原'), findsOneWidget);
    expect(find.textContaining('成品影片也會一起刪除'), findsOneWidget);
    expect(repo.deletedProjects, isEmpty);
  });

  testWidgets('確認視窗按「取消」：不刪除，留在專案總覽', (tester) async {
    final repo = twoProjects();
    final h = await pumpVideo(tester, location: '/videos/p1', repo: repo);
    await tapKey(tester, 'video-project-delete');
    await tapText(tester, '取消');
    expect(repo.deletedProjects, isEmpty);
    expect(h.path, '/videos/p1');
  });

  testWidgets('確認刪除：刪掉後回到專案列表，列表裡沒有這個專案', (tester) async {
    final repo = twoProjects();
    final h = await pumpVideo(tester, location: '/videos/p1', repo: repo);
    await tapKey(tester, 'video-project-delete');
    await tapKey(tester, 'video-project-delete-confirm');
    expect(repo.deletedProjects, ['p1']);
    expect(h.path, '/videos');
    expect(find.text('另一款 規則教學'), findsOneWidget);
    expect(find.text('假遊戲 規則教學'), findsNothing);
  });

  testWidgets('正在產生（409）：顯示後端的說明，留在專案總覽', (tester) async {
    final repo = twoProjects()
      ..deleteProjectError = const ApiException(
        code: 'RULES_VIDEO_PROJECT_BUSY',
        message: '正在產生草稿或影片，完成後再刪除',
        statusCode: 409,
      );
    final h = await pumpVideo(tester, location: '/videos/p1', repo: repo);
    await tapKey(tester, 'video-project-delete');
    await tapKey(tester, 'video-project-delete-confirm');
    expect(find.text('正在產生草稿或影片，完成後再刪除'), findsOneWidget);
    expect(h.path, '/videos/p1');
  });
}
