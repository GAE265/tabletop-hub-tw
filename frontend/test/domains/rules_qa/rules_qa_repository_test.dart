// rules_qa 的 HTTP repository（spec：openspec/changes/add-rules-qa/specs/rules-qa）。
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';

import '../../support/fakes.dart';

RulesQaRepository makeRepository(RecordingAdapter adapter) {
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
  return container.read(rulesQaRepositoryProvider);
}

const lessonJson = '''
{
  "game_id": 3,
  "game_name": "測試桌遊",
  "video": {
    "source": "youtube",
    "video_url": "https://youtu.be/abc123",
    "youtube_id": "abc123",
    "title": "測試桌遊規則教學"
  },
  "has_rulebook": true,
  "suggested_questions": ["怎麼開始一局？", "怎麼計分？"]
}
''';

void main() {
  test('教學清單：GET /api/v1/rules-lessons，解析 snake_case', () async {
    final adapter = RecordingAdapter(
      body:
          '{"items": [{"game_id": 3, "game_name": "測試桌遊", '
          '"has_video": true, "has_rulebook": false}]}',
    );
    final items = await makeRepository(adapter).listLessons();
    expect(adapter.requests.single.method, 'GET');
    expect(adapter.requests.single.uri.path, '/api/v1/rules-lessons');
    expect(items.single.gameId, 3);
    expect(items.single.gameName, '測試桌遊');
    expect(items.single.hasVideo, isTrue);
    expect(items.single.hasRulebook, isFalse);
  });

  test('教學內容：GET /api/v1/rules-lessons/{game_id}，解析影片與建議問題', () async {
    final adapter = RecordingAdapter(body: lessonJson);
    final lesson = await makeRepository(adapter).getLesson(3);
    expect(adapter.requests.single.uri.path, '/api/v1/rules-lessons/3');
    expect(lesson.video!.source, LessonVideoSource.youtube);
    expect(lesson.video!.youtubeId, 'abc123');
    expect(lesson.video!.title, '測試桌遊規則教學');
    expect(lesson.hasRulebook, isTrue);
    expect(lesson.suggestedQuestions, ['怎麼開始一局？', '怎麼計分？']);
  });

  test('教學內容沒有影片：video 為 null', () async {
    final adapter = RecordingAdapter(
      body:
          '{"game_id": 3, "game_name": "測試桌遊", "video": null, '
          '"has_rulebook": true, "suggested_questions": []}',
    );
    final lesson = await makeRepository(adapter).getLesson(3);
    expect(lesson.video, isNull);
  });

  test('發問：POST messages，新對話也要送出 previous_response_id: null', () async {
    final adapter = RecordingAdapter(
      statusCode: 201,
      body:
          '{"response_id": "r-1", "answer": "每個回合抽兩張牌。", '
          '"answerable": true, "citations": [{"page": 3}, {"page": 5}]}',
    );
    final answer = await makeRepository(adapter).sendMessage(
      3,
      const RulesMessageRequest(
        content: '一個回合可以做什麼？',
        previousResponseId: null,
      ),
    );
    final request = adapter.requests.single;
    expect(request.method, 'POST');
    expect(request.uri.path, '/api/v1/rules-lessons/3/messages');
    expect(jsonDecode(adapter.bodies.single!), {
      'content': '一個回合可以做什麼？',
      'previous_response_id': null,
    });
    expect(answer.responseId, 'r-1');
    expect(answer.answerable, isTrue);
    expect(answer.citations.map((c) => c.page), [3, 5]);
  });

  test('後端錯誤轉成 ApiException，保留 code 與 message', () async {
    final adapter = RecordingAdapter(
      statusCode: 409,
      body:
          '{"error": {"code": "RULES_QA_NOT_READY", '
          '"message": "這款遊戲的規則書還沒入庫", "details": {}}}',
    );
    await expectLater(
      makeRepository(adapter).sendMessage(
        3,
        const RulesMessageRequest(content: '怎麼計分？', previousResponseId: null),
      ),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'RULES_QA_NOT_READY')
            .having((e) => e.message, 'message', '這款遊戲的規則書還沒入庫'),
      ),
    );
  });

  test('斷線轉成 NETWORK_ERROR', () async {
    final adapter = RecordingAdapter(
      errorType: DioExceptionType.connectionError,
    );
    await expectLater(
      makeRepository(adapter).listLessons(),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          ApiException.networkErrorCode,
        ),
      ),
    );
  });
}
