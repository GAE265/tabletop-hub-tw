// 規則影片生產器 1d 的 HTTP repository（add-rules-video-mobile MR 6，design.md D12）。
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
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
    final adapter = RecordingAdapter(body: '{"items": [$projectJson], "total": 1}');
    final projects = await makeRepository(adapter).listProjects();
    expect(adapter.requests.single.path, '/api/v1/rules-videos');
    expect(projects.single.chapterTitle, '步驟三');
    expect(projects.single.step, 'draft');
  });

  test('遊戲清單：GET /api/v1/games', () async {
    final adapter = RecordingAdapter(
      body: '{"items": [{"id": 1, "name": "假遊戲", "english_name": "Fake"}], "total": 1}',
    );
    final games = await makeRepository(adapter).listGames();
    expect(adapter.requests.single.path, '/api/v1/games');
    expect(games.single.name, '假遊戲');
  });

  test('建立專案：POST，body 是 snake_case', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: projectJson);
    await makeRepository(adapter).createProject(
      const VideoProjectCreate(gameId: 1, chapterNumber: 11, chapterTitle: '步驟三'),
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
      body: '{"available_pages": [7], "chapter_pages": [7], "reference_pages": [], '
          '"pages_version": 1, "pages": []}',
    );
    await makeRepository(adapter).savePages(
      'p1',
      const VideoPagesUpdate(chapterPages: [7], referencePages: [], texts: {'7': '文字'}),
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
      body: '{"error": {"code": "RULES_VIDEO_DRAFT_NOT_FOUND", "message": "這個專案還沒有草稿", '
          '"details": {}}}',
    );
    expect(await makeRepository(adapter).getDraft('p1'), isNull);
  });
}
