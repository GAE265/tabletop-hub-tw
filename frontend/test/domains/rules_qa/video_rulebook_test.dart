// 店員拍規則書的資料層與 state（2026-11-22 永傑決定）。
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_projects_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_rulebook_state.dart';

import '../../support/fakes.dart';

VideoStudioRepository makeRepository(RecordingAdapter adapter) {
  final container = ProviderContainer(
    overrides: [
      appConfigProvider.overrideWithValue(
        const AppConfig(
          apiBaseUrl: 'http://api.test',
          showPrototypes: false,
          devUserEnabled: false,
        ),
      ),
    ],
  );
  addTearDown(container.dispose);
  container.read(dioProvider).httpClientAdapter = adapter;
  return container.read(videoStudioRepositoryProvider);
}

ProviderContainer makeContainer(
  FakeVideoStudioRepository repo, {
  FakeImagePicker? picker,
}) {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      imagePickerProvider.overrideWithValue(picker ?? FakeImagePicker()),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

PickedImage page(String name) =>
    PickedImage(name: name, bytes: utf8.encode('fake-$name'));

const rulebookJson = '''
{"photos": [{"id": "a1b2", "index": 1, "width": 1512, "height": 2016, "quality": "warn",
  "quality_message": "照片可能不夠清楚，建議重拍"}], "read": true}
''';

void main() {
  group('資料層', () {
    test('讀規則書照片：GET .../rulebook', () async {
      final adapter = RecordingAdapter(body: rulebookJson);
      final rulebook = await makeRepository(adapter).getRulebook('p1');
      expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/rulebook');
      expect(rulebook.read, isTrue);
      final photo = rulebook.photos.single;
      expect(photo.id, 'a1b2');
      expect(photo.quality, 'warn');
      expect(photo.qualityMessage, '照片可能不夠清楚，建議重拍');
    });

    test('上傳一張：POST .../rulebook/photos', () async {
      final adapter = RecordingAdapter(statusCode: 201, body: rulebookJson);
      await makeRepository(adapter).uploadRulebookPhoto('p1', page('p1.jpg'));
      final request = adapter.requests.single;
      expect(request.method, 'POST');
      expect(request.path, '/api/v1/rules-videos/p1/rulebook/photos');
      expect(adapter.bodies.single, contains('p1.jpg'));
    });

    test('刪一張：DELETE .../rulebook/photos/{index}', () async {
      final adapter = RecordingAdapter(statusCode: 204, body: '');
      await makeRepository(adapter).deleteRulebookPhoto('p1', 2);
      expect(adapter.requests.single.method, 'DELETE');
      expect(
        adapter.requests.single.path,
        '/api/v1/rules-videos/p1/rulebook/photos/2',
      );
    });

    test('建立專案：拍規則書時送 rulebook，預設不送', () async {
      final adapter = RecordingAdapter(
        statusCode: 201,
        body:
            '{"id": "p1", "game_id": 1, "game_name": "假遊戲", "shop_id": "s1", '
            '"created_by": "u1", "chapter_number": null, "chapter_title": null, '
            '"title": "假遊戲 規則教學", "step": "rulebook", "rulebook": "photos", '
            '"created_at": "2026-11-22T00:00:00Z", "updated_at": "2026-11-22T00:00:00Z"}',
      );
      final repo = makeRepository(adapter);
      final project = await repo.createProject(
        const VideoProjectCreate(gameId: 1, rulebook: 'photos'),
      );
      await repo.createProject(const VideoProjectCreate(gameId: 1));
      expect(jsonDecode(adapter.bodies[0]!), {
        'game_id': 1,
        'rulebook': 'photos',
      });
      expect(jsonDecode(adapter.bodies[1]!), {'game_id': 1});
      expect(project.rulebook, 'photos');
      expect(project.step, 'rulebook');
    });
  });

  group('規則書照片的 state', () {
    test('載入：依頁的順序列出照片', () async {
      final repo = FakeVideoStudioRepository()
        ..rulebooks['p1'] = Rulebook(
          photos: [sampleRulebookPhoto(), sampleRulebookPhoto(index: 2)],
          read: false,
        );
      final container = makeContainer(repo);
      await container.read(videoRulebookProvider('p1').notifier).load();
      final state = container.read(videoRulebookProvider('p1'));
      expect(state.rulebook!.photos.map((p) => p.index), [1, 2]);
      expect(state.canStart, isTrue);
    });

    test('拍照或選圖：選幾張就依序上傳幾張', () async {
      final repo = FakeVideoStudioRepository();
      final picker = FakeImagePicker()
        ..images = [page('1.jpg'), page('2.jpg'), page('3.jpg')];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      expect(await notifier.addPhotos(), isTrue);
      expect(repo.rulebookUploads.map((u) => u.$2), [
        '1.jpg',
        '2.jpg',
        '3.jpg',
      ]);
      final state = container.read(videoRulebookProvider('p1'));
      expect(state.rulebook!.photos, hasLength(3));
      expect(state.busy, isFalse);
    });

    test('取消選圖：不上傳', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo, picker: FakeImagePicker());
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      expect(await notifier.addPhotos(), isFalse);
      expect(repo.rulebookUploads, isEmpty);
    });

    test('上傳失敗：顯示原因', () async {
      final repo = FakeVideoStudioRepository()
        ..rulebookUploadError = const ApiException(
          code: 'RULES_VIDEO_PHOTO_INVALID',
          message: '只能上傳 JPEG 或 PNG 照片',
          statusCode: 422,
        );
      final picker = FakeImagePicker()..images = [page('x.gif')];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      expect(await notifier.addPhotos(), isFalse);
      expect(
        container.read(videoRulebookProvider('p1')).error,
        '只能上傳 JPEG 或 PNG 照片',
      );
    });

    test('刪一張：後面的往前遞補', () async {
      final repo = FakeVideoStudioRepository()
        ..rulebooks['p1'] = Rulebook(
          photos: [
            sampleRulebookPhoto(),
            sampleRulebookPhoto(index: 2),
            sampleRulebookPhoto(index: 3),
          ],
          read: false,
        );
      final container = makeContainer(repo);
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      await notifier.delete(2);
      expect(repo.rulebookDeletes, [('p1', 2)]);
      expect(
        container
            .read(videoRulebookProvider('p1'))
            .rulebook!
            .photos
            .map((p) => p.id),
        ['f1', 'f3'],
      );
    });

    test('沒有照片、或有太模糊的照片：不能開始', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo);
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      expect(container.read(videoRulebookProvider('p1')).canStart, isFalse);
      repo.rulebooks['p1'] = Rulebook(
        photos: [
          sampleRulebookPhoto(quality: 'bad', qualityMessage: '照片太模糊，請重拍'),
        ],
        read: false,
      );
      await notifier.load();
      final state = container.read(videoRulebookProvider('p1'));
      expect(state.hasBlurry, isTrue);
      expect(state.canStart, isFalse);
    });

    test('讀取規則書並產生草稿：開始草稿工作', () async {
      final repo = FakeVideoStudioRepository()
        ..rulebooks['p1'] = Rulebook(
          photos: [sampleRulebookPhoto()],
          read: false,
        );
      final container = makeContainer(repo);
      final notifier = container.read(videoRulebookProvider('p1').notifier);
      await notifier.load();
      expect(await notifier.start(), isTrue);
      expect(repo.startedDrafts, ['p1']);
    });
  });

  group('建立專案', () {
    test('選「拍規則書」：送出 rulebook=photos', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo);
      final notifier = container.read(videoProjectFormProvider.notifier);
      notifier.selectGame(const VideoGameOption(id: 1, name: '假遊戲'));
      notifier.selectRulebook('photos');
      final project = await notifier.submit();
      expect(repo.created.single.rulebook, 'photos');
      expect(project!.step, 'rulebook');
    });

    test('預設用已匯入的規則書：不送 rulebook', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo);
      final notifier = container.read(videoProjectFormProvider.notifier);
      notifier.selectGame(const VideoGameOption(id: 1, name: '假遊戲'));
      await notifier.submit();
      expect(repo.created.single.rulebook, isNull);
    });
  });
}
