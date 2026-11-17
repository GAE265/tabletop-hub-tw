import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'game_option.dart';

abstract interface class GameSearchRepository {
  Future<List<GameOption>> search(String name);
  Future<List<GameOption>> listAll();
}

class HttpGameSearchRepository implements GameSearchRepository {
  const HttpGameSearchRepository(this._dio);

  final Dio _dio;

  @override
  Future<List<GameOption>> search(String name) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/games',
        queryParameters: {'name': name},
      );
      return GameSearchResult.fromJson(response.data!).items;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  @override
  Future<List<GameOption>> listAll() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/api/v1/games');
      return GameSearchResult.fromJson(response.data!).items;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final gameSearchRepositoryProvider = Provider<GameSearchRepository>(
  (ref) => HttpGameSearchRepository(ref.watch(dioProvider)),
);
