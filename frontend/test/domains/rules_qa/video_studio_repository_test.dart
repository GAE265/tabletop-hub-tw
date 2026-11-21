// 規則影片生產器 1d 的 HTTP repository（add-rules-video-mobile MR 6，design.md D12）。
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';

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

const projectJson = '''
{
  "id": "p1", "game_id": 1, "game_name": "假遊戲", "shop_id": "s1", "created_by": "u1",
  "chapter_number": 11, "chapter_title": "步驟三", "step": "draft",
  "created_at": "2026-11-21T00:00:00Z", "updated_at": "2026-11-21T00:00:00Z"
}
''';

const jobJson = '''
{
  "id": "j1", "project_id": "p1", "kind": "draft", "status": "running", "progress": 0.5,
  "message": "AI 產生草稿", "error": null, "result": null, "created_by": "u1",
  "created_at": "2026-11-21T00:00:00Z", "started_at": "2026-11-21T00:00:01Z",
  "finished_at": null
}
''';

void main() {
  test('專案列表：GET /api/v1/rules-videos，解析 snake_case', () async {
    final adapter = RecordingAdapter(
      body: '{"items": [$projectJson], "total": 1}',
    );
    final projects = await makeRepository(adapter).listProjects();
    expect(adapter.requests.single.path, '/api/v1/rules-videos');
    expect(projects.single.chapterTitle, '步驟三');
    expect(projects.single.step, 'draft');
  });

  test('遊戲清單：GET /api/v1/games', () async {
    final adapter = RecordingAdapter(
      body:
          '{"items": [{"id": 1, "name": "假遊戲", "english_name": "Fake"}], "total": 1}',
    );
    final games = await makeRepository(adapter).listGames();
    expect(adapter.requests.single.path, '/api/v1/games');
    expect(games.single.name, '假遊戲');
  });

  test('建立專案：POST，body 是 snake_case', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: projectJson);
    await makeRepository(adapter).createProject(
      const VideoProjectCreate(
        gameId: 1,
        chapterNumber: 11,
        chapterTitle: '步驟三',
      ),
    );
    expect(adapter.requests.single.method, 'POST');
    expect(jsonDecode(adapter.bodies.single!), {
      'game_id': 1,
      'chapter_number': 11,
      'chapter_title': '步驟三',
    });
  });

  test('存頁面文字：PUT .../pages，texts 的 key 是頁碼字串', () async {
    final adapter = RecordingAdapter(
      body:
          '{"available_pages": [7], "chapter_pages": [7], "reference_pages": [], '
          '"pages_version": 1, "pages": []}',
    );
    await makeRepository(adapter).savePages(
      'p1',
      const VideoPagesUpdate(
        chapterPages: [7],
        referencePages: [],
        texts: {'7': '文字'},
      ),
    );
    expect(adapter.requests.single.method, 'PUT');
    expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/pages');
    expect(jsonDecode(adapter.bodies.single!), {
      'chapter_pages': [7],
      'reference_pages': [],
      'texts': {'7': '文字'},
    });
  });

  test('產生草稿：POST .../jobs，kind=draft', () async {
    final adapter = RecordingAdapter(statusCode: 202, body: jobJson);
    final job = await makeRepository(adapter).startDraft('p1');
    expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/jobs');
    expect(jsonDecode(adapter.bodies.single!), {'kind': 'draft'});
    expect(job.status, VideoJobStatus.running);
    expect(job.message, 'AI 產生草稿');
  });

  test('最近的工作：GET .../jobs?page_size=1；沒有工作回 null', () async {
    final adapter = RecordingAdapter(body: '{"items": [], "total": 0}');
    expect(await makeRepository(adapter).latestJob('p1'), isNull);
    expect(adapter.requests.single.queryParameters['page_size'], 1);
  });

  test('還沒有草稿（404 RULES_VIDEO_DRAFT_NOT_FOUND）回 null', () async {
    final adapter = RecordingAdapter(
      statusCode: 404,
      body:
          '{"error": {"code": "RULES_VIDEO_DRAFT_NOT_FOUND", "message": "這個專案還沒有草稿", '
          '"details": {}}}',
    );
    expect(await makeRepository(adapter).getDraft('p1'), isNull);
  });
  group('素材（MR 8）', () {
    const assetJson = '''
{
  "asset_key": "board", "kind": "flat_photo", "priority": "must", "reason": "圖板",
  "shot": "從正上方拍", "has_photo": true, "orientation": 90,
  "regions": {"zone_a": [0.1, 0.2, 0.3, 0.4], "zone_b": null}, "video_version": 3
}
''';

    test('素材明細：GET .../assets/{key}，區域可以是 null', () async {
      final adapter = RecordingAdapter(body: assetJson);
      final asset = await makeRepository(adapter).getAsset('p1', 'board');
      expect(
        adapter.requests.single.path,
        '/api/v1/rules-videos/p1/assets/board',
      );
      expect(asset.orientation, 90);
      expect(asset.regions, {
        'zone_a': [0.1, 0.2, 0.3, 0.4],
        'zone_b': null,
      });
    });

    test('上傳照片：PUT .../photo，multipart 的 file 欄位', () async {
      final adapter = RecordingAdapter(body: assetJson);
      await makeRepository(adapter).uploadPhoto(
        'p1',
        'board',
        PickedImage(
          name: 'board.jpg',
          bytes: Uint8List.fromList(utf8.encode('img')),
        ),
      );
      final request = adapter.requests.single;
      expect(request.method, 'PUT');
      expect(request.path, '/api/v1/rules-videos/p1/assets/board/photo');
      expect(
        adapter.bodies.single,
        contains('name="file"; filename="board.jpg"'),
      );
    });

    test('讀照片：GET .../photo，回傳位元組', () async {
      final adapter = RecordingAdapter(body: 'PNGDATA');
      final bytes = await makeRepository(adapter).getPhoto('p1', 'board');
      expect(
        adapter.requests.single.path,
        '/api/v1/rules-videos/p1/assets/board/photo',
      );
      expect(bytes, utf8.encode('PNGDATA'));
    });

    test('改方向：PATCH 只送有給的欄位', () async {
      final adapter = RecordingAdapter(body: assetJson);
      await makeRepository(
        adapter,
      ).updateAsset('p1', 'board', const VideoAssetUpdate(orientation: 90));
      expect(adapter.requests.single.method, 'PATCH');
      expect(jsonDecode(adapter.bodies.single!), {'orientation': 90});
    });

    test('改區域：區域給 null 代表改回待量測', () async {
      final adapter = RecordingAdapter(body: assetJson);
      await makeRepository(adapter).updateAsset(
        'p1',
        'board',
        const VideoAssetUpdate(
          regions: {
            'zone_a': [0.1, 0.2, 0.3, 0.4],
            'zone_b': null,
          },
        ),
      );
      expect(jsonDecode(adapter.bodies.single!), {
        'regions': {
          'zone_a': [0.1, 0.2, 0.3, 0.4],
          'zone_b': null,
        },
      });
    });

    test('缺什麼：GET .../readiness', () async {
      final adapter = RecordingAdapter(
        body:
            '{"ready": false, "missing_photos": [{"asset_key": "board", "priority": "optional", '
            '"reason": "圖板", "shot": null}], "missing_regions": [{"asset_key": "board", '
            '"region": "zone_a"}], "unsupported": [{"asset_key": "m", "kind": "drawn", '
            '"message": "本版不支援"}]}',
      );
      final readiness = await makeRepository(adapter).getReadiness('p1');
      expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/readiness');
      expect(readiness.ready, isFalse);
      expect(readiness.missingPhotos.single.priority, 'optional');
      expect(readiness.missingRegions.single.region, 'zone_a');
      expect(readiness.unsupported.single.message, '本版不支援');
    });
  });
}
