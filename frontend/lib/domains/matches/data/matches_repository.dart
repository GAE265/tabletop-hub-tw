import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'game_match.dart';
import 'match_input.dart';

/// 記錄一局遊戲的 API（8 個端點）。所有錯誤都轉成 [ApiException]。
abstract interface class MatchesRepository {
  /// `GET /api/v1/matches`：依日期由新到舊。
  Future<MatchPage> list({
    int? gameId,
    String? groupId,
    String? userId,
    int page = 1,
    int pageSize = 20,
  });

  /// `GET /api/v1/matches/{id}`：含參加者、回合與人數統計。其他人刷新就是重新呼叫這個。
  Future<GameMatch> get(String id);

  /// `POST /api/v1/matches`：開局，開局者自動成為參加者。
  Future<GameMatch> create(MatchInput input);

  /// `POST /api/v1/matches/{id}/participants`：自己加入，或新增沒有帳號的人。
  Future<MatchParticipant> addParticipant(
    String matchId,
    ParticipantInput input,
  );

  /// `PATCH /api/v1/matches/{id}/participants/{participantId}`：本人確認紀錄。
  Future<MatchParticipant> confirm(String matchId, String participantId);

  /// `DELETE /api/v1/matches/{id}/participants/{participantId}`：退出或移除參加者。
  Future<void> removeParticipant(String matchId, String participantId);

  /// `POST /api/v1/matches/{id}/turns`：記錄一個回合。
  ///
  /// 同一回合已有紀錄時後端回 409 `MATCH_TURN_ALREADY_RECORDED`（丟出 [ApiException]，
  /// `details['existing']` 是既有紀錄）；帶 [overwrite] 才覆蓋。[created] 為 false 代表覆蓋了舊紀錄。
  Future<({MatchTurn turn, bool created})> recordTurn(
    String matchId,
    TurnInput input, {
    bool overwrite = false,
  });

  /// `PUT /api/v1/matches/{id}/result`：記錄結果。已有結果時回 409
  /// `MATCH_RESULT_ALREADY_RECORDED`；帶 [overwrite] 才覆蓋（其他人的確認會被清除）。
  Future<GameMatch> recordResult(
    String matchId,
    ResultInput input, {
    bool overwrite = false,
  });
}

class HttpMatchesRepository implements MatchesRepository {
  const HttpMatchesRepository(this._dio);

  final Dio _dio;

  static const _base = '/api/v1/matches';

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  @override
  Future<MatchPage> list({
    int? gameId,
    String? groupId,
    String? userId,
    int page = 1,
    int pageSize = 20,
  }) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      _base,
      queryParameters: {
        'game_id': ?gameId,
        'group_id': ?groupId,
        'user_id': ?userId,
        'page': page,
        'page_size': pageSize,
      },
    );
    return MatchPage.fromJson(response.data!);
  });

  @override
  Future<GameMatch> get(String id) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>('$_base/$id');
    return GameMatch.fromJson(response.data!);
  });

  @override
  Future<GameMatch> create(MatchInput input) => _call(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      _base,
      data: input.toJson(),
    );
    return GameMatch.fromJson(response.data!);
  });

  @override
  Future<MatchParticipant> addParticipant(
    String matchId,
    ParticipantInput input,
  ) => _call(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$matchId/participants',
      data: input.toJson(),
    );
    return MatchParticipant.fromJson(response.data!);
  });

  @override
  Future<MatchParticipant> confirm(String matchId, String participantId) =>
      _call(() async {
        final response = await _dio.patch<Map<String, dynamic>>(
          '$_base/$matchId/participants/$participantId',
          data: {'is_confirmed': true},
        );
        return MatchParticipant.fromJson(response.data!);
      });

  @override
  Future<void> removeParticipant(String matchId, String participantId) => _call(
    () => _dio.delete<void>('$_base/$matchId/participants/$participantId'),
  );

  @override
  Future<({MatchTurn turn, bool created})> recordTurn(
    String matchId,
    TurnInput input, {
    bool overwrite = false,
  }) => _call(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$matchId/turns',
      data: input.toJson(),
      queryParameters: overwrite ? {'overwrite': 'true'} : null,
    );
    return (
      turn: MatchTurn.fromJson(response.data!),
      created: response.statusCode == 201,
    );
  });

  @override
  Future<GameMatch> recordResult(
    String matchId,
    ResultInput input, {
    bool overwrite = false,
  }) => _call(() async {
    final response = await _dio.put<Map<String, dynamic>>(
      '$_base/$matchId/result',
      data: input.toJson(),
      queryParameters: overwrite ? {'overwrite': 'true'} : null,
    );
    return GameMatch.fromJson(response.data!);
  });
}

final matchesRepositoryProvider = Provider<MatchesRepository>(
  (ref) => HttpMatchesRepository(ref.watch(dioProvider)),
);
