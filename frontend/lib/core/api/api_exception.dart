import 'package:dio/dio.dart';

/// 後端統一錯誤格式 `{"error": {"code", "message", "details"}}` 的前端表示。
class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.details = const {},
  });

  /// 無法連線、逾時等沒有收到後端回應的情況。
  static const networkErrorCode = 'NETWORK_ERROR';

  factory ApiException.fromDio(DioException error) {
    final response = error.response;
    final data = response?.data;
    if (data is Map && data['error'] is Map) {
      final body = data['error'] as Map;
      return ApiException(
        code: body['code'] as String? ?? 'UNKNOWN_ERROR',
        message: body['message'] as String? ?? '發生未知錯誤',
        statusCode: response?.statusCode,
        details: (body['details'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
    }
    if (response != null) {
      return ApiException(
        code: 'UNKNOWN_ERROR',
        message: '伺服器回應格式不正確',
        statusCode: response.statusCode,
      );
    }
    return const ApiException(code: networkErrorCode, message: '無法連線到伺服器');
  }

  final String code;
  final String message;
  final int? statusCode;
  final Map<String, dynamic> details;

  @override
  String toString() => 'ApiException($code, $statusCode): $message';
}
