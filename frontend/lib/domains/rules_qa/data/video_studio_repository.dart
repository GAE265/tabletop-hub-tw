import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'video_studio_models.dart';

/// 規則影片生產器 1d 的 API（add-rules-video-mobile design.md D1、D2、D11）。
/// 失敗時拋 [ApiException]；斷線、逾時的 `code` 是 `NETWORK_ERROR`。
abstract interface class VideoStudioRepository {
  /// 自己店的影片專案（管理員看全部），新的在前。
  Future<List<VideoProject>> listProjects();

  /// 建立專案時可選的遊戲。
  Future<List<VideoGameOption>> listGames();

  Future<VideoProject> createProject(VideoProjectCreate input);

  Future<VideoProject> getProject(String projectId);

  /// 可選的頁、選了的頁、每頁的原文與編輯後的文字、差異。
  Future<VideoPages> getPages(String projectId);

  /// 存選頁與編輯後的文字（整份取代；沒給文字的頁用原文）。
  Future<VideoPages> savePages(String projectId, VideoPagesUpdate input);

  /// 建立草稿工作（202）。已有進行中的工作時拋 `RULES_VIDEO_JOB_RUNNING`（details.job_id）。
  Future<VideoJob> startDraft(String projectId);

  Future<VideoJob> getJob(String projectId, String jobId);

  /// 最近一個工作；沒有工作時是 null。
  Future<VideoJob?> latestJob(String projectId);

  /// 草稿；還沒有草稿時是 null。
  Future<VideoDraft?> getDraft(String projectId);
}

class HttpVideoStudioRepository implements VideoStudioRepository {
  const HttpVideoStudioRepository(this._dio);

  final Dio _dio;

  static const _base = '/api/v1/rules-videos';

  @override
  Future<List<VideoProject>> listProjects() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      _base,
      queryParameters: {'page': 1, 'page_size': 100},
    );
    return [
      for (final item in response.data!['items'] as List<dynamic>)
        VideoProject.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<List<VideoGameOption>> listGames() => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/games',
      queryParameters: {'page': 1, 'page_size': 100},
    );
    return [
      for (final item in response.data!['items'] as List<dynamic>)
        VideoGameOption.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<VideoProject> createProject(VideoProjectCreate input) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          _base,
          data: input.toJson(),
        );
        return VideoProject.fromJson(response.data!);
      });

  @override
  Future<VideoProject> getProject(String projectId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>('$_base/$projectId');
    return VideoProject.fromJson(response.data!);
  });

  @override
  Future<VideoPages> getPages(String projectId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_base/$projectId/pages',
    );
    return VideoPages.fromJson(response.data!);
  });

  @override
  Future<VideoPages> savePages(String projectId, VideoPagesUpdate input) =>
      _guard(() async {
        final response = await _dio.put<Map<String, dynamic>>(
          '$_base/$projectId/pages',
          data: input.toJson(),
        );
        return VideoPages.fromJson(response.data!);
      });

  @override
  Future<VideoJob> startDraft(String projectId) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$projectId/jobs',
      data: {'kind': 'draft'},
    );
    return VideoJob.fromJson(response.data!);
  });

  @override
  Future<VideoJob> getJob(String projectId, String jobId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_base/$projectId/jobs/$jobId',
    );
    return VideoJob.fromJson(response.data!);
  });

  @override
  Future<VideoJob?> latestJob(String projectId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_base/$projectId/jobs',
      queryParameters: {'page': 1, 'page_size': 1},
    );
    final items = response.data!['items'] as List<dynamic>;
    return items.isEmpty
        ? null
        : VideoJob.fromJson(items.first as Map<String, dynamic>);
  });

  @override
  Future<VideoDraft?> getDraft(String projectId) async {
    try {
      return await _guard(() async {
        final response = await _dio.get<Map<String, dynamic>>(
          '$_base/$projectId/draft',
        );
        return VideoDraft.fromJson(response.data!);
      });
    } on ApiException catch (error) {
      if (error.code == 'RULES_VIDEO_DRAFT_NOT_FOUND') return null;
      rethrow;
    }
  }

  Future<T> _guard<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final videoStudioRepositoryProvider = Provider<VideoStudioRepository>(
  (ref) => HttpVideoStudioRepository(ref.watch(dioProvider)),
);
