import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'advisor_message.dart';

/// 等推薦 Agent 回應的上限：比後端最壞的 3 次 × 30 秒 = 90 秒長（spec §14.1）。
/// 只設在這個請求，不改 core/api 的共用設定。
const advisorReceiveTimeout = Duration(seconds: 100);

abstract interface class AdvisorRepository {
  /// 送出一則訊息。失敗時拋 [ApiException]；斷線、逾時的 `code` 是 `NETWORK_ERROR`。
  Future<AdvisorMessageResponse> sendMessage(AdvisorMessageRequest request);
}

class HttpAdvisorRepository implements AdvisorRepository {
  const HttpAdvisorRepository(this._dio);

  final Dio _dio;

  @override
  Future<AdvisorMessageResponse> sendMessage(
    AdvisorMessageRequest request,
  ) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/advisor/messages',
        data: request.toJson(),
        options: Options(receiveTimeout: advisorReceiveTimeout),
      );
      return AdvisorMessageResponse.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final advisorRepositoryProvider = Provider<AdvisorRepository>(
  (ref) => HttpAdvisorRepository(ref.watch(dioProvider)),
);
