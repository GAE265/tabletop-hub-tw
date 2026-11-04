import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'health_status.dart';

abstract interface class HealthRepository {
  Future<HealthStatus> fetch();
}

class HttpHealthRepository implements HealthRepository {
  const HttpHealthRepository(this._dio);

  final Dio _dio;

  @override
  Future<HealthStatus> fetch() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/api/v1/health');
      return HealthStatus.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final healthRepositoryProvider = Provider<HealthRepository>(
  (ref) => HttpHealthRepository(ref.watch(dioProvider)),
);
