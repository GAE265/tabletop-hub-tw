import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'host_models.dart';

/// 語音主持的三個一般請求（host spec §11）。失敗時一律拋 [ApiException]。
abstract interface class HostingSessionsRepository {
  /// 自己還保留著的主持（0 或 1 筆）。
  Future<List<HostingSession>> list();

  /// 開一場主持；已有的那場會被取代。
  Future<HostingSessionAccess> create(CreateHostingSessionRequest request);

  /// 拿一次性通行碼。帶 [turnTakingMode] 而且和現在不同時，就是切換接話方式。
  Future<HostingSessionAccess> connect(
    String id, {
    TurnTakingMode? turnTakingMode,
  });
}

class HttpHostingSessionsRepository implements HostingSessionsRepository {
  const HttpHostingSessionsRepository(this._dio);

  final Dio _dio;

  // ⚠️ 必須和後端 host 的 router 同步。
  static const _base = '/api/v1/hosting-sessions';

  @override
  Future<List<HostingSession>> list() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(_base);
    final items = response.data!['items'] as List<dynamic>;
    return [
      for (final item in items)
        HostingSession.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<HostingSessionAccess> create(CreateHostingSessionRequest request) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          _base,
          data: request.toJson(),
        );
        return HostingSessionAccess.fromJson(response.data!);
      });

  @override
  Future<HostingSessionAccess> connect(
    String id, {
    TurnTakingMode? turnTakingMode,
  }) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$id/connections',
      data: {'turn_taking_mode': ?turnTakingMode?.wire},
    );
    return HostingSessionAccess.fromJson(response.data!);
  });

  Future<T> _guard<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final hostingSessionsRepositoryProvider = Provider<HostingSessionsRepository>(
  (ref) => HttpHostingSessionsRepository(ref.watch(dioProvider)),
);
