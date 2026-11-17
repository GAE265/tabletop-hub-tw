import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'group.dart';
import 'group_input.dart';

/// 揪團 API。所有錯誤都轉成 [ApiException]。
abstract interface class GroupsRepository {
  /// `GET /api/v1/groups`：依開始時間區間查詢（不含已取消的揪團）。
  Future<GroupPage> list({
    DateTime? startFrom,
    DateTime? startBefore,
    int page = 1,
    int pageSize = 20,
  });

  Future<Group> get(String id);

  Future<List<GroupMember>> listMembers(String id);

  Future<Group> create(GroupInput input);

  /// `PATCH /api/v1/groups/{id}`；取消揪團是 `{"status": "cancelled"}`。
  Future<Group> update(String id, Map<String, dynamic> changes);

  /// 報名；額滿時加入候補。
  Future<JoinResult> join(String id);

  /// 退出，或由開團主移除成員。
  Future<void> removeMember(String groupId, String userId);

  /// 開團表單的店家選項（`GET /api/v1/shops`，booking 的 API）。
  Future<List<ShopRef>> listShops();

  /// 依名稱搜尋遊戲（`GET /api/v1/games?q=`），最多 20 筆。
  Future<List<GameRef>> searchGames(String query);
}

class HttpGroupsRepository implements GroupsRepository {
  const HttpGroupsRepository(this._dio);

  final Dio _dio;

  static const _base = '/api/v1/groups';

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  @override
  Future<GroupPage> list({
    DateTime? startFrom,
    DateTime? startBefore,
    int page = 1,
    int pageSize = 20,
  }) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      _base,
      queryParameters: {
        if (startFrom != null)
          'start_from': startFrom.toUtc().toIso8601String(),
        if (startBefore != null)
          'start_before': startBefore.toUtc().toIso8601String(),
        'page': page,
        'page_size': pageSize,
      },
    );
    return GroupPage.fromJson(response.data!);
  });

  @override
  Future<Group> get(String id) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>('$_base/$id');
    return Group.fromJson(response.data!);
  });

  @override
  Future<List<GroupMember>> listMembers(String id) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>('$_base/$id/members');
    final items = response.data!['items'] as List<dynamic>;
    return [
      for (final item in items)
        GroupMember.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<Group> create(GroupInput input) => _call(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      _base,
      data: input.toJson(),
    );
    return Group.fromJson(response.data!);
  });

  @override
  Future<Group> update(String id, Map<String, dynamic> changes) =>
      _call(() async {
        final response = await _dio.patch<Map<String, dynamic>>(
          '$_base/$id',
          data: changes,
        );
        return Group.fromJson(response.data!);
      });

  @override
  Future<JoinResult> join(String id) => _call(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$id/members',
    );
    return JoinResult.fromJson(response.data!);
  });

  @override
  Future<void> removeMember(String groupId, String userId) =>
      _call(() => _dio.delete<void>('$_base/$groupId/members/$userId'));

  @override
  Future<List<ShopRef>> listShops() => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/shops');
    final items = response.data!['items'] as List<dynamic>;
    return [
      for (final item in items) ShopRef.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<List<GameRef>> searchGames(String query) => _call(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/games',
      queryParameters: {'q': query, 'page_size': 20},
    );
    final items = response.data!['items'] as List<dynamic>;
    return [
      for (final item in items) GameRef.fromJson(item as Map<String, dynamic>),
    ];
  });
}

final groupsRepositoryProvider = Provider<GroupsRepository>(
  (ref) => HttpGroupsRepository(ref.watch(dioProvider)),
);
