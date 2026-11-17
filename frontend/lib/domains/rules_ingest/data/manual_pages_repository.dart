import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/platform/image_picker.dart';
import 'manual_page.dart';

abstract interface class ManualPagesRepository {
  Future<ManualPage> importPage(int gamesId, int page, PickedImage image);
  Future<ManualPageList> list(int gamesId);
}

class HttpManualPagesRepository implements ManualPagesRepository {
  const HttpManualPagesRepository(this._dio);
  final Dio _dio;

  @override
  Future<ManualPage> importPage(
    int gamesId,
    int page,
    PickedImage image,
  ) async {
    try {
      final response = await _dio.put<Map<String, dynamic>>(
        '/api/v1/games/$gamesId/manual-pages/$page',
        data: FormData.fromMap({
          'file': MultipartFile.fromBytes(image.bytes, filename: image.name),
        }),
        options: Options(
          sendTimeout: const Duration(seconds: 180),
          receiveTimeout: const Duration(seconds: 180),
        ),
      );
      return ManualPage.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  @override
  Future<ManualPageList> list(int gamesId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/games/$gamesId/manual-pages',
      );
      return ManualPageList.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}

final manualPagesRepositoryProvider = Provider<ManualPagesRepository>(
  (ref) => HttpManualPagesRepository(ref.watch(dioProvider)),
);
