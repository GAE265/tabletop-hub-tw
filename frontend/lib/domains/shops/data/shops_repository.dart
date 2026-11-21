import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'shop_models.dart';

abstract interface class ShopsRepository {
  /// 新增店家。店員新增後，後端會把他的帳號綁到新店。
  Future<CreatedShop> createShop({
    required String name,
    String? phone,
    String? address,
  });

  /// 這間店的庫存，依加入先後排。
  Future<List<ShopGame>> listGames(String shopId);

  Future<ShopGame> addGame(String shopId, int gameId);

  Future<void> removeGame(String shopId, int gameId);

  /// 全部桌遊，供「加入庫存」挑選。
  Future<List<GameChoice>> listGameChoices();
}

class HttpShopsRepository implements ShopsRepository {
  const HttpShopsRepository(this._dio);

  final Dio _dio;

  Future<T> _call<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  @override
  Future<CreatedShop> createShop({
    required String name,
    String? phone,
    String? address,
  }) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/shops',
      data: {'name': name, 'phone': ?phone, 'address': ?address},
    );
    return CreatedShop.fromJson(r.data!);
  });

  @override
  Future<List<ShopGame>> listGames(String shopId) => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/api/v1/shops/$shopId/games',
    );
    return [
      for (final i in r.data!['items'] as List)
        ShopGame.fromJson(i as Map<String, dynamic>),
    ];
  });

  @override
  Future<ShopGame> addGame(String shopId, int gameId) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/shops/$shopId/games',
      data: {'game_id': gameId},
    );
    return ShopGame.fromJson(r.data!);
  });

  @override
  Future<void> removeGame(String shopId, int gameId) => _call(() async {
    await _dio.delete<void>('/api/v1/shops/$shopId/games/$gameId');
  });

  @override
  Future<List<GameChoice>> listGameChoices() => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>('/api/v1/games');
    return [
      for (final i in r.data!['items'] as List)
        GameChoice.fromJson(i as Map<String, dynamic>),
    ];
  });
}

final shopsRepositoryProvider = Provider<ShopsRepository>(
  (ref) => HttpShopsRepository(ref.watch(dioProvider)),
);
