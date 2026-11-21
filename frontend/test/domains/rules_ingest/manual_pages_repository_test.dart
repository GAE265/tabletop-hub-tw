import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_page.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';

import '../../support/fakes.dart';

void main() {
  test('multipart 使用 file 欄位、保留位元組、路徑與逾時', () async {
    final adapter = FakeManualPagesAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://api.test'))
      ..httpClientAdapter = adapter;
    addTearDown(dio.close);
    final repository = HttpManualPagesRepository(dio);
    final page = await repository.importPage(
      1,
      1,
      PickedImage(name: 'sample.png', bytes: Uint8List.fromList([65, 66, 67])),
    );
    expect(page.content, '# title');
    expect(page.chunkCount, 2);
    expect(adapter.requests.single.path, '/api/v1/games/1/manual-pages/1');
    expect(adapter.requests.single.method, 'PUT');
    expect(
      adapter.requests.single.receiveTimeout,
      const Duration(seconds: 180),
    );
    expect(adapter.bodies.single, contains('name="file"'));
    expect(adapter.bodies.single, contains('filename="sample.png"'));
    expect(adapter.bodies.single, contains('ABC'));
  });

  test('讀回 DTO 正確對應 snake_case 與空文字', () async {
    final adapter = FakeManualPagesAdapter()
      ..response = {
        'items': [
          {'page': 1, 'content': ''},
        ],
        'total': 1,
        'ocr_provider': 'cloud',
      };
    final dio = Dio(BaseOptions(baseUrl: 'http://api.test'))
      ..httpClientAdapter = adapter;
    addTearDown(dio.close);
    final result = await HttpManualPagesRepository(dio).list(9);
    expect(result.ocrProvider, 'cloud');
    expect(result.items.single, const ManualPage(page: 1, content: ''));
    expect(result.items.single.chunkCount, 0);
    expect(adapter.requests.single.path, '/api/v1/games/9/manual-pages');
  });

  test('HTTP 錯誤保留統一的後端訊息與錯誤碼', () async {
    final adapter = FakeManualPagesAdapter()
      ..status = 403
      ..response = {
        'error': {
          'code': 'PERMISSION_DENIED',
          'message': '沒有權限',
          'details': {},
        },
      };
    final dio = Dio(BaseOptions(baseUrl: 'http://api.test'))
      ..httpClientAdapter = adapter;
    addTearDown(dio.close);
    await expectLater(
      HttpManualPagesRepository(dio).list(1),
      throwsA(
        isA<ApiException>()
            .having((e) => e.message, 'message', '沒有權限')
            .having((e) => e.statusCode, 'statusCode', 403),
      ),
    );
  });
}
