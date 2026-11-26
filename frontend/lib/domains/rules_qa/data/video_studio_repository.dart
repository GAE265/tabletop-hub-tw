import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/platform/image_picker.dart';
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

  /// 建立草稿工作（202）。已有進行中的工作時拋 `RULES_VIDEO_JOB_RUNNING`（details.job_id）。
  Future<VideoJob> startDraft(String projectId);

  Future<VideoJob> getJob(String projectId, String jobId);

  /// 最近一個工作；沒有工作時是 null。
  Future<VideoJob?> latestJob(String projectId);

  /// 草稿；還沒有草稿時是 null。
  Future<VideoDraft?> getDraft(String projectId);

  /// 一個素材的方向、區域座標、有沒有照片（MR 7）。
  Future<VideoAsset> getAsset(String projectId, String assetKey);

  /// 上傳或換一張照片（JPEG、PNG，最多 15 MB）；後端依 EXIF 轉正，方向改回 0。
  Future<VideoAsset> uploadPhoto(
    String projectId,
    String assetKey,
    PickedImage image,
  );

  /// 照片的內容（帶身分讀取，見 design.md D13 待決 1）。
  Future<Uint8List> getPhoto(String projectId, String assetKey);

  /// 改方向或區域座標。
  Future<VideoAsset> updateAsset(
    String projectId,
    String assetKey,
    VideoAssetUpdate input,
  );

  /// 換某一段某一格的素材（放牌的格子指定哪一張的正面或牌背）。
  /// 版本不同時拋 `RULES_VIDEO_CONFLICT`（409）。
  Future<SegmentSwapResult> swapSegmentAsset(
    String projectId,
    String segmentKey,
    SegmentSwapInput input,
  );

  /// 新增一個照片素材（換素材完整版）。同名時拋 `RULES_VIDEO_ASSET_LABEL_TAKEN`（422）。
  Future<VideoAsset> createAsset(String projectId, VideoAssetCreate input);

  /// 產生影片前還缺什麼。
  Future<VideoReadiness> getReadiness(String projectId);

  /// 建立產生影片的工作（202）。素材沒齊時拋 `RULES_VIDEO_NOT_READY`（MR 9）。
  Future<VideoJob> startRender(String projectId);

  /// 最近一次成功的成品；還沒有時是 null。
  Future<VideoRender?> getRender(String projectId);

  /// 成品的影片檔（帶身分讀取，整支下載）。
  Future<Uint8List> getRenderVideo(String projectId);

  /// 照片模式專案的規則書照片（店員拍規則書）。
  Future<Rulebook> getRulebook(String projectId);

  /// 加一張規則書照片（排在最後）。
  Future<Rulebook> uploadRulebookPhoto(String projectId, PickedImage image);

  /// 刪掉第 index 張（後面的往前遞補）。
  Future<void> deleteRulebookPhoto(String projectId, int index);

  /// 第 index 張的圖檔（帶身分讀取）。
  Future<Uint8List> getRulebookPhoto(String projectId, int index);

  /// 刪除專案（無法復原；照片與成品影片一起刪）。正在產生時後端回 409。
  Future<void> deleteProject(String projectId);

  /// 用一句話修改：送出修改要求，建立修改的工作（AI 算出提案，不寫入草稿）。
  Future<VideoRevision> createRevision(
    String projectId,
    VideoRevisionCreate input,
  );

  /// 看修改的進度與結果。
  Future<VideoRevision> getRevision(String projectId, String revisionId);

  /// 套用提案或選的替代做法。
  Future<VideoRevision> applyRevision(
    String projectId,
    String revisionId,
    VideoRevisionApply input,
  );
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

  @override
  Future<VideoAsset> getAsset(String projectId, String assetKey) =>
      _guard(() async {
        final response = await _dio.get<Map<String, dynamic>>(
          '$_base/$projectId/assets/$assetKey',
        );
        return VideoAsset.fromJson(response.data!);
      });

  @override
  Future<VideoAsset> uploadPhoto(
    String projectId,
    String assetKey,
    PickedImage image,
  ) => _guard(() async {
    final response = await _dio.put<Map<String, dynamic>>(
      '$_base/$projectId/assets/$assetKey/photo',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(image.bytes, filename: image.name),
      }),
    );
    return VideoAsset.fromJson(response.data!);
  });

  @override
  Future<Uint8List> getPhoto(String projectId, String assetKey) =>
      _guard(() async {
        final response = await _dio.get<List<int>>(
          '$_base/$projectId/assets/$assetKey/photo',
          options: Options(responseType: ResponseType.bytes),
        );
        return Uint8List.fromList(response.data!);
      });

  @override
  Future<SegmentSwapResult> swapSegmentAsset(
    String projectId,
    String segmentKey,
    SegmentSwapInput input,
  ) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '$_base/$projectId/segments/$segmentKey',
      data: input.toJson(),
    );
    return SegmentSwapResult.fromJson(response.data!);
  });

  @override
  Future<VideoAsset> createAsset(String projectId, VideoAssetCreate input) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '$_base/$projectId/assets',
          data: input.toJson(),
        );
        return VideoAsset.fromJson(response.data!);
      });

  @override
  Future<VideoAsset> updateAsset(
    String projectId,
    String assetKey,
    VideoAssetUpdate input,
  ) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '$_base/$projectId/assets/$assetKey',
      data: input.toJson(),
    );
    return VideoAsset.fromJson(response.data!);
  });

  @override
  Future<VideoReadiness> getReadiness(String projectId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_base/$projectId/readiness',
    );
    return VideoReadiness.fromJson(response.data!);
  });

  @override
  Future<VideoJob> startRender(String projectId) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$projectId/jobs',
      data: {'kind': 'render'},
    );
    return VideoJob.fromJson(response.data!);
  });

  @override
  Future<VideoRender?> getRender(String projectId) async {
    try {
      return await _guard(() async {
        final response = await _dio.get<Map<String, dynamic>>(
          '$_base/$projectId/render',
        );
        return VideoRender.fromJson(response.data!);
      });
    } on ApiException catch (error) {
      if (error.code == 'RULES_VIDEO_RENDER_NOT_FOUND') return null;
      rethrow;
    }
  }

  @override
  Future<Uint8List> getRenderVideo(String projectId) => _guard(() async {
    final response = await _dio.get<List<int>>(
      '$_base/$projectId/render/video',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(response.data!);
  });

  @override
  Future<Rulebook> getRulebook(String projectId) => _guard(() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_base/$projectId/rulebook',
    );
    return Rulebook.fromJson(response.data!);
  });

  @override
  Future<Rulebook> uploadRulebookPhoto(String projectId, PickedImage image) =>
      _guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '$_base/$projectId/rulebook/photos',
          data: FormData.fromMap({
            'file': MultipartFile.fromBytes(image.bytes, filename: image.name),
          }),
        );
        return Rulebook.fromJson(response.data!);
      });

  @override
  Future<VideoRevision> createRevision(
    String projectId,
    VideoRevisionCreate input,
  ) => _guard(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_base/$projectId/revisions',
      data: input.toJson(),
    );
    return VideoRevision.fromJson(response.data!);
  });

  @override
  Future<VideoRevision> getRevision(String projectId, String revisionId) =>
      _guard(() async {
        final response = await _dio.get<Map<String, dynamic>>(
          '$_base/$projectId/revisions/$revisionId',
        );
        return VideoRevision.fromJson(response.data!);
      });

  @override
  Future<VideoRevision> applyRevision(
    String projectId,
    String revisionId,
    VideoRevisionApply input,
  ) => _guard(() async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '$_base/$projectId/revisions/$revisionId',
      data: input.toJson(),
    );
    return VideoRevision.fromJson(response.data!);
  });

  @override
  Future<void> deleteProject(String projectId) => _guard(() async {
    await _dio.delete<void>('$_base/$projectId');
  });

  @override
  Future<void> deleteRulebookPhoto(String projectId, int index) =>
      _guard(() async {
        await _dio.delete<void>('$_base/$projectId/rulebook/photos/$index');
      });

  @override
  Future<Uint8List> getRulebookPhoto(String projectId, int index) =>
      _guard(() async {
        final response = await _dio.get<List<int>>(
          '$_base/$projectId/rulebook/photos/$index',
          options: Options(responseType: ResponseType.bytes),
        );
        return Uint8List.fromList(response.data!);
      });

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
