import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'rules_qa_models.dart';

/// 等規則問答回應的上限：後端檢索加上 LLM 回答，用語不符時還會改寫一次。
/// 只設在發問這個請求，不改 core/api 的共用設定。
const rulesQaReceiveTimeout = Duration(seconds: 100);

abstract interface class RulesQaRepository {
  /// 有教材的遊戲。失敗時拋 [ApiException]。
  Future<List<RulesLessonSummary>> listLessons();

  /// 某款遊戲的教學內容。沒有教材時拋 `RULES_LESSON_NOT_FOUND`。
  Future<RulesLesson> getLesson(int gameId);

  /// 發問。失敗時拋 [ApiException]；斷線、逾時的 `code` 是 `NETWORK_ERROR`。
  Future<RulesAnswer> sendMessage(int gameId, RulesMessageRequest request);
}

class HttpRulesQaRepository implements RulesQaRepository {
  const HttpRulesQaRepository(this._dio);

  final Dio _dio;

  static const _base = '/api/v1/rules-lessons';

  @override
  Future<List<RulesLessonSummary>> listLessons() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(_base);
    final items = response.data!['items'] as List<dynamic>;
    return [
      for (final item in items)
        RulesLessonSummary.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<RulesLesson> getLesson(int gameId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>('$_base/$gameId');
    return RulesLesson.fromJson(response.data!);
  });

  @override
  Future<RulesAnswer> sendMessage(int gameId, RulesMessageRequest request) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '$_base/$gameId/messages',
          data: request.toJson(),
          options: Options(receiveTimeout: rulesQaReceiveTimeout),
        );
        return RulesAnswer.fromJson(response.data!);
      });

  Future<T> _guard<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final rulesQaRepositoryProvider = Provider<RulesQaRepository>(
  (ref) => HttpRulesQaRepository(ref.watch(dioProvider)),
);
