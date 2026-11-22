// 店員拍規則書的畫面（2026-11-22 永傑決定）：建立時選「拍規則書」、專案總覽多一步「規則書」、
// 規則書頁（拍照或選圖、清晰度提示、刪除、讀取規則書並產生草稿）。
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../../support/fakes.dart';
import 'video_pages_support.dart';

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

PickedImage page(String name) =>
    PickedImage(name: name, bytes: utf8.encode('fake-$name'));

FakeVideoStudioRepository photoRepo({Rulebook? rulebook}) {
  final repo = FakeVideoStudioRepository(
    projects: [sampleVideoProject(step: 'rulebook', rulebook: 'photos')],
    games: const [VideoGameOption(id: 1, name: '假遊戲')],
  );
  if (rulebook != null) repo.rulebooks['p1'] = rulebook;
  return repo;
}

void main() {
  group('建立專案', () {
    testWidgets('選「拍規則書」：建立後直接到規則書頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/new',
        repo: photoRepo(),
      );
      await tester.tap(find.byKey(const Key('video-project-game')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('假遊戲').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-project-rulebook-photos');
      expect(find.text('建立並拍規則書'), findsOneWidget);
      await tapKey(tester, 'video-project-submit');
      expect(h.repo.created.single.rulebook, 'photos');
      expect(h.path, '/videos/p-new/rulebook');
    });
  });

  group('專案總覽', () {
    testWidgets('照片模式：四個步驟，目前在「規則書」，下一步是拍規則書', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: photoRepo(),
      );
      expect(find.text('規則書'), findsOneWidget);
      expect(find.byKey(const Key('video-step-3')), findsOneWidget);
      await tapKey(tester, 'video-next-step');
      expect(h.path, '/videos/p1/rulebook');
    });
  });

  group('規則書頁', () {
    testWidgets('還沒有照片：說明要依順序拍每一頁，不能開始', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/rulebook',
        repo: photoRepo(),
      );
      expect(find.textContaining('依頁面的順序'), findsOneWidget);
      expect(find.text('還沒有照片'), findsOneWidget);
      final start = tester.widget<FilledButton>(
        find.byKey(const Key('video-rulebook-start')),
      );
      expect(start.onPressed, isNull);
    });

    testWidgets('拍照或選圖：依序列出「第 N 張」，可以刪除', (tester) async {
      final picker = FakeImagePicker()..images = [page('1.jpg'), page('2.jpg')];
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/rulebook',
        repo: photoRepo(),
        picker: picker,
      );
      await tapKey(tester, 'video-rulebook-add');
      expect(find.text('第 1 張'), findsOneWidget);
      expect(find.text('第 2 張'), findsOneWidget);
      await tapKey(tester, 'video-rulebook-delete-1');
      expect(h.repo.rulebookDeletes, [('p1', 1)]);
      expect(find.text('第 2 張'), findsNothing);
    });

    testWidgets('太模糊的照片：寫出請重拍，不能開始', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/rulebook',
        repo: photoRepo(
          rulebook: Rulebook(
            photos: [
              sampleRulebookPhoto(),
              sampleRulebookPhoto(
                index: 2,
                quality: 'bad',
                qualityMessage: '照片太模糊，請重拍',
              ),
            ],
            read: false,
          ),
        ),
      );
      expect(find.text('照片太模糊，請重拍'), findsOneWidget);
      expect(find.textContaining('刪掉後重拍'), findsOneWidget);
      final start = tester.widget<FilledButton>(
        find.byKey(const Key('video-rulebook-start')),
      );
      expect(start.onPressed, isNull);
    });

    testWidgets('讀取規則書並產生草稿：開始工作並回到專案總覽', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/rulebook',
        repo: photoRepo(
          rulebook: Rulebook(photos: [sampleRulebookPhoto()], read: false),
        ),
      );
      h.repo.jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      await tapKey(tester, 'video-rulebook-start');
      expect(h.repo.startedDrafts, ['p1']);
      expect(h.path, '/videos/p1');
      await stopPolling(tester);
    });

    testWidgets('都讀過了：提示重新產生草稿不會再讀', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/rulebook',
        repo: photoRepo(
          rulebook: Rulebook(photos: [sampleRulebookPhoto()], read: true),
        ),
      );
      expect(find.textContaining('已經讀過'), findsOneWidget);
    });
  });
}
