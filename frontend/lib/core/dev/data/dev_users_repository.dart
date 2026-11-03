import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/api_client.dart';
import '../../api/api_exception.dart';
import 'dev_user.dart';

abstract interface class DevUsersRepository {
  Future<List<DevUser>> list();
}

class HttpDevUsersRepository implements DevUsersRepository {
  const HttpDevUsersRepository(this._dio);

  final Dio _dio;

  @override
  Future<List<DevUser>> list() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/dev/users',
      );
      final items = response.data!['items'] as List<dynamic>;
      return [
        for (final item in items)
          DevUser.fromJson(item as Map<String, dynamic>),
      ];
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final devUsersRepositoryProvider = Provider<DevUsersRepository>(
  (ref) => HttpDevUsersRepository(ref.watch(rawDioProvider)),
);
