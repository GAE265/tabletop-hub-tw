// 8 個端點的路徑、方法、參數與錯誤轉換（AGENTS.md 4.3 的 API 契約）。
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/data/match_input.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';

/// 記下每個請求，並依 [handler] 回應；不連網路。
class RecordingAdapter implements HttpClientAdapter {
  RecordingAdapter(this.handler);

  ResponseBody Function(RequestOptions options) handler;
  final requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody json(Object body, [int status = 200]) => ResponseBody.fromString(
  jsonEncode(body),
  status,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

const participantJson = {
  'id': 'p-1',
  'seat_number': 1,
  'user_id': 'u-1',
  'display_name': '測試玩家',
  'faction': null,
  'score': null,
  'placement': null,
  'is_winner': null,
  'is_confirmed': false,
};

const turnJson = {
  'id': 't-1',
  'turn_number': 1,
  'seat_number': 2,
  'game_data': {
    'played_seat_numbers': [1, 2],
  },
  'recorded_by': 'u-1',
  'updated_at': '2026-11-20T12:00:00Z',
};

const matchJson = {
  'id': 'm-1',
  'game': {'id': 1, 'name': '血與刃的白薔薇'},
  'played_on': '2026-11-20',
  'location_type': 'shop',
  'shop': {'id': 's-1', 'name': '測試桌遊店'},
  'group_id': null,
  'created_by': {'id': 'u-1', 'display_name': '測試玩家'},
  'status': 'in_progress',
  'result': null,
  'progress': null,
  'participants': [participantJson],
  'turns': [turnJson],
  'participant_count': 1,
  'account_count': 1,
  'confirmed_count': 0,
  'is_valid': false,
  'created_at': '2026-11-20T12:00:00Z',
  'updated_at': '2026-11-20T12:00:00Z',
};

(HttpMatchesRepository, RecordingAdapter) make(
  ResponseBody Function(RequestOptions) handler,
) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test'));
  final adapter = RecordingAdapter(handler);
  dio.httpClientAdapter = adapter;
  return (HttpMatchesRepository(dio), adapter);
}

void main() {
  test('get：GET /matches/{id}，解析參加者、回合與人數統計', () async {
    final (repo, adapter) = make((_) => json(matchJson));
    final match = await repo.get('m-1');
    final request = adapter.requests.single;
    expect((request.method, request.path), ('GET', '/api/v1/matches/m-1'));
    expect(match.game.name, '血與刃的白薔薇');
    expect(match.playedOn, DateTime(2026, 11, 20)); // 沒有時區的日曆日期
    expect(match.shop?.name, '測試桌遊店');
    expect(match.participants.single.userId, 'u-1');
    expect(match.participants.single.isWinner, isNull);
    expect(match.turns.single.gameData['played_seat_numbers'], [1, 2]);
    expect(
      (match.participantCount, match.accountCount, match.confirmedCount),
      (1, 1, 0),
    );
    expect(match.isValid, isFalse);
  });

  test('list：GET /matches 帶篩選與分頁', () async {
    final (repo, adapter) = make(
      (_) => json({
        'items': [matchJson],
        'total': 1,
      }),
    );
    final page = await repo.list(gameId: 1, groupId: 'g-1', userId: 'u-1');
    final request = adapter.requests.single;
    expect((request.method, request.path), ('GET', '/api/v1/matches'));
    expect(request.queryParameters, {
      'game_id': 1,
      'group_id': 'g-1',
      'user_id': 'u-1',
      'page': 1,
      'page_size': 20,
    });
    expect(page.total, 1);
    expect(page.items.single.id, 'm-1');
  });

  test('create：POST /matches，日期用 yyyy-MM-dd，自家不帶店家', () async {
    final (repo, adapter) = make((_) => json(matchJson, 201));
    await repo.create(
      MatchInput(
        gameId: 1,
        playedOn: DateTime(2026, 1, 5),
        locationType: 'home',
        seatNumber: 4,
      ),
    );
    final request = adapter.requests.single;
    expect((request.method, request.path), ('POST', '/api/v1/matches'));
    expect(request.data, {
      'game_id': 1,
      'played_on': '2026-01-05',
      'location_type': 'home',
      'seat_number': 4,
    });
  });

  test('addParticipant：POST /matches/{id}/participants', () async {
    final (repo, adapter) = make((_) => json(participantJson, 201));
    final self = await repo.addParticipant('m-1', const ParticipantInput());
    await repo.addParticipant(
      'm-1',
      const ParticipantInput(displayName: 'Amy', seatNumber: 3),
    );
    expect(adapter.requests.map((r) => (r.method, r.path)), [
      ('POST', '/api/v1/matches/m-1/participants'),
      ('POST', '/api/v1/matches/m-1/participants'),
    ]);
    expect(adapter.requests[0].data, <String, dynamic>{});
    expect(adapter.requests[1].data, {'display_name': 'Amy', 'seat_number': 3});
    expect(self.displayName, '測試玩家');
  });

  test('confirm：PATCH /matches/{id}/participants/{pid}，只送 true', () async {
    final (repo, adapter) = make(
      (_) => json({...participantJson, 'is_confirmed': true}),
    );
    final confirmed = await repo.confirm('m-1', 'p-1');
    final request = adapter.requests.single;
    expect(
      (request.method, request.path),
      ('PATCH', '/api/v1/matches/m-1/participants/p-1'),
    );
    expect(request.data, {'is_confirmed': true});
    expect(confirmed.isConfirmed, isTrue);
  });

  test('removeParticipant：DELETE /matches/{id}/participants/{pid}', () async {
    final (repo, adapter) = make((_) => ResponseBody.fromString('', 204));
    await repo.removeParticipant('m-1', 'p-1');
    final request = adapter.requests.single;
    expect(
      (request.method, request.path),
      ('DELETE', '/api/v1/matches/m-1/participants/p-1'),
    );
  });

  group('recordTurn', () {
    const input = TurnInput(
      turnNumber: 1,
      seatNumber: 2,
      gameData: {
        'played_seat_numbers': [1, 2],
      },
    );

    test('新增：POST /turns，201 代表新增', () async {
      final (repo, adapter) = make((_) => json(turnJson, 201));
      final saved = await repo.recordTurn('m-1', input);
      final request = adapter.requests.single;
      expect(
        (request.method, request.path),
        ('POST', '/api/v1/matches/m-1/turns'),
      );
      expect(request.queryParameters, isEmpty);
      expect(request.data, input.toJson());
      expect(saved.created, isTrue);
      expect(saved.turn.turnNumber, 1);
    });

    test('覆蓋：帶 overwrite=true，200 代表覆蓋', () async {
      final (repo, adapter) = make((_) => json(turnJson));
      final saved = await repo.recordTurn('m-1', input, overwrite: true);
      expect(adapter.requests.single.queryParameters, {'overwrite': 'true'});
      expect(saved.created, isFalse);
    });

    test('同一回合已有紀錄：409 轉成 ApiException，保留既有紀錄', () async {
      final (repo, _) = make(
        (_) => json({
          'error': {
            'code': 'MATCH_TURN_ALREADY_RECORDED',
            'message': '第 1 回合已經有紀錄',
            'details': {
              'existing': {'turn_number': 1, 'seat_number': 3},
            },
          },
        }, 409),
      );
      await expectLater(
        repo.recordTurn('m-1', input),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'MATCH_TURN_ALREADY_RECORDED')
              .having((e) => e.statusCode, 'statusCode', 409)
              .having(
                (e) => (e.details['existing'] as Map)['seat_number'],
                'existing.seat_number',
                3,
              ),
        ),
      );
    });
  });

  test('recordResult：PUT /result，覆蓋時帶 overwrite=true', () async {
    final (repo, adapter) = make((_) => json(matchJson));
    const input = ResultInput(
      winningFaction: 'rose',
      factions: {1: 'rose', 2: 'blood_blade'},
    );
    await repo.recordResult('m-1', input);
    await repo.recordResult('m-1', input, overwrite: true);
    expect(adapter.requests.map((r) => (r.method, r.path)), [
      ('PUT', '/api/v1/matches/m-1/result'),
      ('PUT', '/api/v1/matches/m-1/result'),
    ]);
    expect(adapter.requests[0].queryParameters, isEmpty);
    expect(adapter.requests[1].queryParameters, {'overwrite': 'true'});
    expect(adapter.requests[0].data, {
      'winning_faction': 'rose',
      'participants': [
        {'seat_number': 1, 'faction': 'rose'},
        {'seat_number': 2, 'faction': 'blood_blade'},
      ],
    });
  });

  test('連不上伺服器：NETWORK_ERROR', () async {
    final (repo, _) = make(
      (options) => throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline',
      ),
    );
    await expectLater(
      repo.get('m-1'),
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
