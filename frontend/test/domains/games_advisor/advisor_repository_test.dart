import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';

import '../../support/fakes.dart';

// spec §14.2 的 data/ 測試表，加上 MR 說明標 ➕ 的情境。

const responseJson = '''
{
  "response_id": "resp_1",
  "reply": "幫你找到 1 款適合 4 個人、輕鬆聊天的桌遊。",
  "relaxed_constraint": "playtime",
  "recommendations": [
    {
      "game": {
        "id": 1, "name": "範例桌遊甲",
        "min_players": 2, "max_players": 4,
        "min_playtime": 30, "max_playtime": 45,
        "min_age": 10, "weight": 1.85
      },
      "reason": "規則簡單、不燒腦。",
      "excerpts": [{"id": "e1", "text": "一局節奏很快", "language": "zh-TW"}]
    }
  ]
}
''';

const emptyResponseJson = '''
{"response_id": null, "reply": "你們有幾個人？", "relaxed_constraint": null, "recommendations": []}
''';

AdvisorMessageResponse parse(String json) =>
    AdvisorMessageResponse.fromJson(jsonDecode(json) as Map<String, dynamic>);

/// 用 core/api 的 dioProvider 組出 repository，請求交給 [adapter]。
AdvisorRepository makeRepository(RecordingAdapter adapter) {
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
  return container.read(advisorRepositoryProvider);
}

TypeMatcher<ApiException> apiExceptionWithCode(String code) =>
    isA<ApiException>().having((e) => e.code, 'code', code);

void main() {
  group('解析回應', () {
    test('1 張卡片、relaxed_constraint 是 playtime：每個欄位都對到', () {
      final response = parse(responseJson);

      expect(response.responseId, 'resp_1');
      expect(response.reply, '幫你找到 1 款適合 4 個人、輕鬆聊天的桌遊。');
      expect(response.relaxedConstraint, RelaxedConstraint.playtime);
      final card = response.recommendations.single;
      expect(card.reason, '規則簡單、不燒腦。');
      expect(
        card.game,
        const AdvisorGame(
          id: 1,
          name: '範例桌遊甲',
          minPlayers: 2,
          maxPlayers: 4,
          minPlaytime: 30,
          maxPlaytime: 45,
          minAge: 10,
          weight: 1.85,
        ),
      );
      expect(card.excerpts, const [
        AdvisorExcerpt(id: 'e1', text: '一局節奏很快', language: 'zh-TW'),
      ]);
    });

    test('relaxed_constraint 是 null、recommendations 是空的：解析成功', () {
      final response = parse(emptyResponseJson);

      expect(response.responseId, isNull);
      expect(response.reply, '你們有幾個人？');
      expect(response.relaxedConstraint, isNull);
      expect(response.recommendations, isEmpty);
    });
  });

  group('送出訊息', () {
    test(
      'POST /api/v1/advisor/messages，body 是 content 與 previous_response_id，接收逾時 100 秒',
      () async {
        final adapter = RecordingAdapter(statusCode: 201, body: responseJson);
        final repository = makeRepository(adapter);

        final response = await repository.sendMessage(
          const AdvisorMessageRequest(
            content: '想輕鬆聊天',
            previousResponseId: 'resp_0',
          ),
        );

        final request = adapter.requests.single;
        expect(request.method, 'POST');
        expect(request.path, '/api/v1/advisor/messages');
        expect(request.receiveTimeout, const Duration(seconds: 100));
        expect(jsonDecode(adapter.bodies.single!), {
          'content': '想輕鬆聊天',
          'previous_response_id': 'resp_0',
        });
        expect(response.responseId, 'resp_1');
      },
    );

    test('新對話：body 一定帶 "previous_response_id": null，不能省略', () async {
      final adapter = RecordingAdapter(
        statusCode: 201,
        body: emptyResponseJson,
      );
      final repository = makeRepository(adapter);

      await repository.sendMessage(
        const AdvisorMessageRequest(content: '4 人', previousResponseId: null),
      );

      final body = jsonDecode(adapter.bodies.single!) as Map<String, dynamic>;
      expect(body.containsKey('previous_response_id'), isTrue);
      expect(body['previous_response_id'], isNull);
    });

    test('後端回錯誤格式：拋 ApiException，code 是後端的 error.code', () async {
      final adapter = RecordingAdapter(
        statusCode: 503,
        body:
            '{"error": {"code": "GAMES_ADVISOR_UNAVAILABLE", '
            '"message": "推薦 Agent 暫時無法回應", "details": {}}}',
      );
      final repository = makeRepository(adapter);

      await expectLater(
        repository.sendMessage(
          const AdvisorMessageRequest(content: '4 人', previousResponseId: null),
        ),
        throwsA(
          apiExceptionWithCode(
            'GAMES_ADVISOR_UNAVAILABLE',
          ).having((e) => e.statusCode, 'statusCode', 503),
        ),
      );
    });

    for (final (name, type) in [
      ('等太久', DioExceptionType.receiveTimeout),
      ('斷線', DioExceptionType.connectionError),
    ]) {
      test('$name：拋 ApiException，code 是 NETWORK_ERROR', () async {
        final repository = makeRepository(RecordingAdapter(errorType: type));

        await expectLater(
          repository.sendMessage(
            const AdvisorMessageRequest(
              content: '4 人',
              previousResponseId: null,
            ),
          ),
          throwsA(apiExceptionWithCode(ApiException.networkErrorCode)),
        );
      });
    }
  });
}
