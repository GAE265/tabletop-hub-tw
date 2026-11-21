// host 的一般請求（host spec §11）。
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/hosting_sessions_repository.dart';

import '../../support/fakes.dart';

HostingSessionsRepository makeRepository(RecordingAdapter adapter) {
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
  return container.read(hostingSessionsRepositoryProvider);
}

const sessionJson = '''
{
  "id": "h-1",
  "status": "active",
  "player_count": 7,
  "turn_taking_mode": "push_to_talk",
  "voice": "female",
  "step": "turn",
  "turn_number": 2,
  "phase_number": 3,
  "paused": false,
  "winner": null,
  "created_at": "2026-11-22T12:00:00Z"
}
''';

const accessJson =
    '{"session": $sessionJson, "connection": {"ticket": "t-abc", "expires_at": "2026-11-22T12:01:00Z"}}';

void main() {
  test('開主持：POST /api/v1/hosting-sessions，送 snake_case，解析通行碼', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: accessJson);
    final access = await makeRepository(adapter).create(
      const CreateHostingSessionRequest(
        playerCount: 7,
        turnTakingMode: TurnTakingMode.pushToTalk,
        voice: HostVoice.female,
      ),
    );

    expect(adapter.requests.single.method, 'POST');
    expect(adapter.requests.single.path, '/api/v1/hosting-sessions');
    expect(jsonDecode(adapter.bodies.single!), {
      'player_count': 7,
      'turn_taking_mode': 'push_to_talk',
      'voice': 'female',
    });
    expect(access.connection.ticket, 't-abc');
    expect(access.connection.expiresAt, DateTime.utc(2026, 11, 22, 12, 1));
    final session = access.session;
    expect(session.id, 'h-1');
    expect(session.status, HostStatus.active);
    expect(session.turnTakingMode, TurnTakingMode.pushToTalk);
    expect(session.voice, HostVoice.female);
    expect(session.step, HostStep.turn);
    expect(session.turnNumber, 2);
    expect(session.phaseNumber, 3);
    expect(session.winner, isNull);
  });

  test('列出自己的主持：GET /api/v1/hosting-sessions，解析 items', () async {
    final adapter = RecordingAdapter(
      body: '{"items": [$sessionJson], "total": 1}',
    );
    final sessions = await makeRepository(adapter).list();
    expect(adapter.requests.single.method, 'GET');
    expect(adapter.requests.single.path, '/api/v1/hosting-sessions');
    expect(sessions.single.id, 'h-1');
  });

  test('拿通行碼：不帶接話方式時 body 是空物件', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: accessJson);
    await makeRepository(adapter).connect('h-1');
    expect(adapter.requests.single.method, 'POST');
    expect(
      adapter.requests.single.path,
      '/api/v1/hosting-sessions/h-1/connections',
    );
    expect(jsonDecode(adapter.bodies.single!), <String, dynamic>{});
  });

  test('拿通行碼並切換接話方式：帶 turn_taking_mode', () async {
    final adapter = RecordingAdapter(statusCode: 201, body: accessJson);
    await makeRepository(
      adapter,
    ).connect('h-1', turnTakingMode: TurnTakingMode.pushToTalk);
    expect(jsonDecode(adapter.bodies.single!), {
      'turn_taking_mode': 'push_to_talk',
    });
  });

  test('節點代號：night_1、night_2 對應到夜晚兩步，贏的一方照代號解析', () {
    final session = HostingSession.fromJson({
      ...jsonDecode(sessionJson) as Map<String, dynamic>,
      'status': 'ended',
      'step': 'night_2',
      'turn_number': null,
      'phase_number': null,
      'winner': 'blood_blade',
    });
    expect(session.step, HostStep.night2);
    expect(session.status, HostStatus.ended);
    expect(session.winner, HostWinner.bloodBlade);
    expect(
      HostingSession.fromJson({
        ...jsonDecode(sessionJson) as Map<String, dynamic>,
        'step': 'night_1',
        'winner': 'white_rose',
      }),
      isA<HostingSession>()
          .having((s) => s.step, 'step', HostStep.night1)
          .having((s) => s.winner, 'winner', HostWinner.whiteRose),
    );
  });

  test('後端錯誤：轉成 ApiException，帶 code 與狀態碼', () async {
    final adapter = RecordingAdapter(
      statusCode: 404,
      body:
          '{"error": {"code": "HOST_SESSION_NOT_FOUND", "message": "找不到", "details": {}}}',
    );
    await expectLater(
      makeRepository(adapter).connect('h-x'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'HOST_SESSION_NOT_FOUND')
            .having((e) => e.statusCode, 'statusCode', 404),
      ),
    );
  });

  test('連不上後端：ApiException 的 code 是 NETWORK_ERROR', () async {
    final adapter = RecordingAdapter(
      errorType: DioExceptionType.connectionError,
    );
    await expectLater(
      makeRepository(adapter).list(),
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
