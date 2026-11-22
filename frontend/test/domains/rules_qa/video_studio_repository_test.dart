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
  "chapter_number": null, "chapter_title": null, "title": "假遊戲 規則教學", "step": "draft",
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
    expect(projects.single.title, '假遊戲 規則教學');
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

  test('建立專案：POST，只送遊戲（整個遊戲一支影片）', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: projectJson);
    final project = await makeRepository(
      adapter,
    ).createProject(const VideoProjectCreate(gameId: 1));
    expect(adapter.requests.single.method, 'POST');
    expect(jsonDecode(adapter.bodies.single!), {'game_id': 1});
    expect(project.chapterNumber, isNull);
    expect(project.title, '假遊戲 規則教學');
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
            '"skippable": true, "reason": "圖板", "shot": null}], "missing_regions": [{"asset_key": "board", '
            '"region": "zone_a"}], "unsupported": [{"asset_key": "m", "kind": "drawn", '
            '"message": "本版不支援"}]}',
      );
      final readiness = await makeRepository(adapter).getReadiness('p1');
      expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/readiness');
      expect(readiness.ready, isFalse);
      expect(readiness.missingPhotos.single.priority, 'optional');
      expect(readiness.missingPhotos.single.skippable, isTrue);
      expect(readiness.missingRegions.single.region, 'zone_a');
      expect(readiness.unsupported.single.message, '本版不支援');
    });
  });
  group('產生影片（MR 10）', () {
    test('產生影片：POST .../jobs，kind=render', () async {
      final adapter = RecordingAdapter(
        statusCode: 202,
        body: jobJson.replaceFirst('"kind": "draft"', '"kind": "render"'),
      );
      final job = await makeRepository(adapter).startRender('p1');
      expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/jobs');
      expect(jsonDecode(adapter.bodies.single!), {'kind': 'render'});
      expect(job.kind, 'render');
    });

    test('成品：GET .../render', () async {
      final adapter = RecordingAdapter(
        body:
            '{"job_id": "j9", "video_path": "/api/v1/rules-videos/p1/render/video", '
            '"total_seconds": 42.5, "reencoded": ["s1"], "reused": ["s2"], '
            '"skipped_assets": ["blue"], "estimated": true, "warnings": [], '
            '"finished_at": "2026-11-22T00:00:00Z"}',
      );
      final render = await makeRepository(adapter).getRender('p1');
      expect(adapter.requests.single.path, '/api/v1/rules-videos/p1/render');
      expect(render!.totalSeconds, 42.5);
      expect(render.reencoded, ['s1']);
      expect(render.skippedAssets, ['blue']);
    });

    test('還沒有成品（404 RULES_VIDEO_RENDER_NOT_FOUND）回 null', () async {
      final adapter = RecordingAdapter(
        statusCode: 404,
        body:
            '{"error": {"code": "RULES_VIDEO_RENDER_NOT_FOUND", "message": "還沒有", '
            '"details": {}}}',
      );
      expect(await makeRepository(adapter).getRender('p1'), isNull);
    });

    test('影片檔：GET .../render/video，回傳位元組', () async {
      final adapter = RecordingAdapter(body: 'MP4DATA');
      final bytes = await makeRepository(adapter).getRenderVideo('p1');
      expect(
        adapter.requests.single.path,
        '/api/v1/rules-videos/p1/render/video',
      );
      expect(bytes, utf8.encode('MP4DATA'));
    });

    test('略過：PATCH 只送 skipped', () async {
      final adapter = RecordingAdapter(
        body:
            '{"asset_key": "blue", "kind": "flat_photo", "priority": "optional", '
            '"reason": "藍牌", "shot": null, "has_photo": false, "orientation": 0, '
            '"regions": {}, "video_version": 2, "skipped": true, "skippable": true, '
            '"skip_affected_segments": [1], "skip_blocked_segments": []}',
      );
      final asset = await makeRepository(
        adapter,
      ).updateAsset('p1', 'blue', const VideoAssetUpdate(skipped: true));
      expect(jsonDecode(adapter.bodies.single!), {'skipped': true});
      expect(asset.skipped, isTrue);
      expect(asset.skippable, isTrue);
      expect(asset.skipAffectedSegments, [1]);
    });
  });
}
