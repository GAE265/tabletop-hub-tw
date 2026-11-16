import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/state/manual_pages_state.dart';

import '../../support/fakes.dart';

PickedImage image(String name) =>
    PickedImage(name: name, bytes: Uint8List.fromList([1, 2, 3]));

ProviderContainer containerFor(
  FakeManualPagesRepository repo,
  FakeImagePicker picker,
) {
  final container = ProviderContainer(
    overrides: [
      manualPagesRepositoryProvider.overrideWithValue(repo),
      imagePickerProvider.overrideWithValue(picker),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('檔名排序、指定起始頁碼、逐頁送出並自動讀回', () async {
    final repo = FakeManualPagesRepository();
    final picker = FakeImagePicker()
      ..images = [image('c.png'), image('a.png'), image('b.png')];
    final container = containerFor(repo, picker);
    final notifier = container.read(manualImportProvider.notifier);
    notifier.setGamesInput('12');
    notifier.setStartPageInput('5');
    await notifier.pickImages();
    expect(container.read(manualImportProvider).images.map((i) => i.name), [
      'a.png',
      'b.png',
      'c.png',
    ]);
    await notifier.importPages();
    expect(repo.imports.map((call) => call.page), [5, 6, 7]);
    expect(repo.imports.map((call) => call.gamesId), [12, 12, 12]);
    expect(repo.maxActive, 1);
    expect(repo.lists, [12]);
    expect(
      container.read(manualImportProvider).results.every((r) => r.success),
      isTrue,
    );
    expect(container.read(manualPagesProvider).data!.total, 3);
  });

  test('第二頁失敗不中止，結果保留後端錯誤訊息', () async {
    final repo = FakeManualPagesRepository()
      ..failures[2] = const ApiException(
        code: 'OCR_UNAVAILABLE',
        message: '稍後再試',
        statusCode: 503,
      );
    final picker = FakeImagePicker()
      ..images = [image('a.png'), image('b.png'), image('c.png')];
    final container = containerFor(repo, picker);
    final notifier = container.read(manualImportProvider.notifier)
      ..setGamesInput('1');
    await notifier.pickImages();
    await notifier.importPages();
    expect(repo.imports.map((c) => c.page), [1, 2, 3]);
    final results = container.read(manualImportProvider).results;
    expect(results.map((r) => r.success), [true, false, true]);
    expect(results[1].error, '稍後再試');
    expect(container.read(manualPagesProvider).data!.items.map((p) => p.page), [
      1,
      3,
    ]);
  });

  test('匯入期間防止重送、改欄位與重選圖片，顯示當前進度', () async {
    final repo = FakeManualPagesRepository()..importGate = Completer<void>();
    final picker = FakeImagePicker()..images = [image('a.png'), image('b.png')];
    final container = containerFor(repo, picker);
    final notifier = container.read(manualImportProvider.notifier)
      ..setGamesInput('1');
    await notifier.pickImages();
    final pending = notifier.importPages();
    expect(container.read(manualImportProvider).importing, isTrue);
    expect(container.read(manualImportProvider).current, 1);
    expect(container.read(manualImportProvider).canImport, isFalse);
    await notifier.importPages();
    await notifier.pickImages();
    notifier.setGamesInput('99');
    expect(repo.imports.length, 1);
    expect(picker.calls, 1);
    repo.importGate!.complete();
    await pending;
    expect(repo.imports.map((c) => c.gamesId), [1, 1]);
    expect(container.read(manualImportProvider).importing, isFalse);
  });

  for (final input in ['', 'abc', '0', '-1', '1.5']) {
    test('無效桌遊編號 $input 不送出 API', () async {
      final repo = FakeManualPagesRepository();
      final picker = FakeImagePicker()..images = [image('a.png')];
      final container = containerFor(repo, picker);
      final notifier = container.read(manualImportProvider.notifier)
        ..setGamesInput(input);
      await notifier.pickImages();
      await notifier.importPages();
      await container.read(manualPagesProvider.notifier).load(input);
      expect(repo.imports, isEmpty);
      expect(repo.lists, isEmpty);
      expect(container.read(manualImportProvider).error, isNotNull);
    });
  }

  test('缺圖片或起始頁碼小於 1 不送出 API', () async {
    final repo = FakeManualPagesRepository();
    final picker = FakeImagePicker()..images = [image('a.png')];
    final container = containerFor(repo, picker);
    final notifier = container.read(manualImportProvider.notifier)
      ..setGamesInput('1');
    await notifier.importPages();
    expect(repo.imports, isEmpty);
    await notifier.pickImages();
    notifier.setStartPageInput('0');
    await notifier.importPages();
    expect(repo.imports, isEmpty);
    expect(container.read(manualImportProvider).canImport, isFalse);
  });

  test('取消選檔保留原圖，選檔失敗可重試', () async {
    final repo = FakeManualPagesRepository();
    final picker = FakeImagePicker()..images = [image('a.png')];
    final container = containerFor(repo, picker);
    final notifier = container.read(manualImportProvider.notifier);
    await notifier.pickImages();
    picker.images = null;
    await notifier.pickImages();
    expect(container.read(manualImportProvider).images.length, 1);
    picker.error = StateError('read failed');
    await notifier.pickImages();
    expect(container.read(manualImportProvider).error, isNotNull);
    expect(container.read(manualImportProvider).picking, isFalse);
  });

  test('讀回載入中、排序、空文字與 OCR provider', () async {
    final repo = FakeManualPagesRepository()
      ..rows[3] = 'three'
      ..rows[1] = ''
      ..ocrProvider = 'cloud'
      ..listGate = Completer<void>();
    final container = containerFor(repo, FakeImagePicker());
    final pending = container.read(manualPagesProvider.notifier).load('1');
    expect(container.read(manualPagesProvider).loading, isTrue);
    repo.listGate!.complete();
    await pending;
    final state = container.read(manualPagesProvider);
    expect(state.loading, isFalse);
    expect(state.data!.items.map((p) => p.page), [1, 3]);
    expect(state.data!.items.first.content, '');
    expect(state.data!.ocrProvider, 'cloud');
  });

  test('空列表與 fake provider', () async {
    final container = containerFor(
      FakeManualPagesRepository(),
      FakeImagePicker(),
    );
    await container.read(manualPagesProvider.notifier).load('1');
    expect(container.read(manualPagesProvider).data!.items, isEmpty);
    expect(container.read(manualPagesProvider).data!.ocrProvider, 'fake');
  });

  test('404 保留成功列表，403 提示切換身分', () async {
    final repo = FakeManualPagesRepository()..rows[1] = 'saved';
    final container = containerFor(repo, FakeImagePicker());
    final notifier = container.read(manualPagesProvider.notifier);
    await notifier.load('1');
    repo.listError = const ApiException(
      code: 'GAME_NOT_FOUND',
      message: '桌遊不存在',
      statusCode: 404,
    );
    await notifier.load('999');
    expect(container.read(manualPagesProvider).error, '桌遊不存在');
    expect(
      container.read(manualPagesProvider).data!.items.first.content,
      'saved',
    );
    expect(container.read(manualPagesProvider).gamesId, 1);
    repo.listError = const ApiException(
      code: 'PERMISSION_DENIED',
      message: '沒有權限',
      statusCode: 403,
    );
    await notifier.load('1');
    expect(
      container.read(manualPagesProvider).error,
      contains('shop_staff 或 admin'),
    );
  });
}
