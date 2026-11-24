// 規則影片素材的 state（add-rules-video-mobile MR 8，design.md D14）。
import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_image_size.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_state.dart';

import '../../support/fakes.dart';
import 'video_assets_support.dart';

const ref = (projectId: 'p1', assetKey: 'board');

ProviderContainer makeContainer(
  FakeVideoStudioRepository repo, {
  FakeImagePicker? picker,
}) {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      imagePickerProvider.overrideWithValue(picker ?? FakeImagePicker()),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('圖片大小', () {
    test('PNG 與 JPEG 從檔頭讀出寬高', () {
      expect(imageSizeOf(pngBytes), const Size(40, 20));
      expect(imageSizeOf(jpegBytes), const Size(30, 60));
    });

    test('不是圖片：null', () {
      expect(imageSizeOf(Uint8List.fromList([1, 2, 3])), isNull);
    });

    test('方向 90、270 時寬高對調', () {
      expect(displaySize(const Size(40, 20), 90), const Size(20, 40));
      expect(displaySize(const Size(40, 20), 180), const Size(40, 20));
    });
  });

  group('缺什麼', () {
    test('讀 readiness', () async {
      final container = makeContainer(assetsRepo());
      final readiness = await container.read(
        videoReadinessProvider('p1').future,
      );
      expect(readiness.ready, isFalse);
      expect(readiness.missingPhotos, hasLength(2));
    });
  });

  group('單一素材', () {
    test('載入：有照片時一起讀圖', () async {
      final repo = assetsRepo(
        asset: sampleAsset(hasPhoto: true),
        photo: pngBytes,
      );
      final container = makeContainer(repo);
      await container.read(videoAssetProvider(ref).notifier).load();
      final state = container.read(videoAssetProvider(ref));
      expect(state.asset?.assetKey, 'board');
      expect(state.photo, pngBytes);
    });

    test('拍照上傳：顯示存好的照片（後端可能轉正過），重新讀 readiness', () async {
      final repo = assetsRepo()..storedPhoto = (_) => jpegBytes;
      final picker = FakeImagePicker()..images = [picked()];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await container.read(videoReadinessProvider('p1').future);
      repo.readiness['p1'] = readyNone;

      await notifier.pickAndUpload();
      final state = container.read(videoAssetProvider(ref));
      expect(repo.uploads.single.$3.bytes, pngBytes);
      expect(state.asset!.hasPhoto, isTrue);
      expect(state.photo, jpegBytes);
      expect(state.photoReplaced, isFalse); // 第一次拍，不用提示
      expect(
        (await container.read(videoReadinessProvider('p1').future)).ready,
        isTrue,
      );
    });

    test('換照片且有區域：提示重新確認區域', () async {
      final repo = assetsRepo(
        asset: sampleAsset(
          hasPhoto: true,
          regions: {
            'zone_a': [0.1, 0.1, 0.2, 0.2],
          },
        ),
        photo: pngBytes,
      );
      final picker = FakeImagePicker()..images = [picked(jpegBytes)];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await notifier.pickAndUpload();
      expect(container.read(videoAssetProvider(ref)).photoReplaced, isTrue);
    });

    // 原本（2026-11-22）選到 HEIC 就擋下；iPhone 實測選圖設定不列 HEIC 仍會交出 HEIC，
    // 2026-11-24 永傑決定改由後端轉成 JPEG，前端照常上傳
    test('選到 HEIC：照常上傳（後端會轉成 JPEG），沒有錯誤訊息', () async {
      final repo = assetsRepo()..storedPhoto = (_) => jpegBytes;
      final picker = FakeImagePicker()
        ..images = [PickedImage(name: 'IMG_0001.HEIC', bytes: heicBytes())];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await notifier.pickAndUpload();
      expect(repo.uploads.single.$3.name, 'IMG_0001.HEIC');
      expect(container.read(videoAssetProvider(ref)).error, isNull);
    });

    test('取消選圖：不上傳', () async {
      final repo = assetsRepo();
      final container = makeContainer(repo, picker: FakeImagePicker());
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await notifier.pickAndUpload();
      expect(repo.uploads, isEmpty);
    });

    test('上傳失敗（格式、大小）：顯示原因', () async {
      final repo = assetsRepo()
        ..uploadError = const ApiException(
          code: 'RULES_VIDEO_PHOTO_TOO_LARGE',
          message: '照片太大，每張最多 15 MB',
          statusCode: 422,
        );
      final picker = FakeImagePicker()..images = [picked()];
      final container = makeContainer(repo, picker: picker);
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await notifier.pickAndUpload();
      final state = container.read(videoAssetProvider(ref));
      expect(state.error, '照片太大，每張最多 15 MB');
      expect(state.busy, isFalse);
    });

    test('旋轉：每次順時針 90 度，270 之後回到 0', () async {
      final repo = assetsRepo(
        asset: sampleAsset(hasPhoto: true, orientation: 270),
        photo: pngBytes,
      );
      final container = makeContainer(repo);
      final notifier = container.read(videoAssetProvider(ref).notifier);
      await notifier.load();
      await notifier.rotate();
      expect(repo.updates.single.$3.orientation, 0);
      expect(repo.updates.single.$3.regions, isNull);
      expect(container.read(videoAssetProvider(ref)).asset!.orientation, 0);
    });
  });

  group('標區域', () {
    FakeVideoStudioRepository regionsRepo({
      Map<String, List<double>?> regions = const {
        'zone_a': [0.1, 0.1, 0.2, 0.2],
        'zone_b': null,
      },
    }) => assetsRepo(
      asset: sampleAsset(hasPhoto: true, regions: regions),
      photo: pngBytes,
    );

    test('載入：已標的與待標的；目前選第一個還沒標的', () async {
      final container = makeContainer(regionsRepo());
      await container.read(videoRegionsProvider(ref).notifier).load();
      final state = container.read(videoRegionsProvider(ref));
      expect(state.names, ['zone_a', 'zone_b']);
      expect(state.doneCount, 1);
      expect(state.current, 'zone_b');
      expect(state.dirty, isFalse);
    });

    test('拖出區域後儲存：存相對比例，只送改過的區域', () async {
      final repo = regionsRepo();
      final container = makeContainer(repo);
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      notifier.setBox('zone_b', const Rect.fromLTWH(0.5, 0.25, 0.25, 0.5));
      final state = container.read(videoRegionsProvider(ref));
      expect(state.doneCount, 2);
      expect(state.dirty, isTrue);
      expect(state.canSave, isTrue);

      expect(await notifier.save(), isTrue);
      expect(repo.updates.single.$3.regions, {
        'zone_b': [0.5, 0.25, 0.25, 0.5],
      });
      expect(container.read(videoRegionsProvider(ref)).dirty, isFalse);
    });

    test('框超出照片：裁在 0–1 之內', () async {
      final container = makeContainer(regionsRepo());
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      notifier.setBox('zone_b', const Rect.fromLTRB(-0.2, 0.5, 0.5, 1.3));
      expect(
        container.read(videoRegionsProvider(ref)).boxes['zone_b'],
        const Rect.fromLTRB(0, 0.5, 0.5, 1),
      );
    });

    test('框太小（寬或高 < 1%）：不能儲存', () async {
      final container = makeContainer(regionsRepo());
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      notifier.setBox('zone_b', const Rect.fromLTWH(0.5, 0.5, 0.005, 0.3));
      final state = container.read(videoRegionsProvider(ref));
      expect(state.tooSmall, ['zone_b']);
      expect(state.canSave, isFalse);
    });

    test('儲存失敗：顯示原因，改過的框保留', () async {
      final repo = regionsRepo()
        ..updateError = const ApiException(
          code: 'RULES_VIDEO_CONFLICT',
          message: '專案剛被修改',
          statusCode: 409,
        );
      final container = makeContainer(repo);
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      notifier.setBox('zone_b', const Rect.fromLTWH(0.5, 0.25, 0.25, 0.5));
      expect(await notifier.save(), isFalse);
      final state = container.read(videoRegionsProvider(ref));
      expect(state.error, '專案剛被修改');
      expect(state.dirty, isTrue);
    });

    // 2026-11-22 永傑決定：標區域畫面顯示白話說明與「第 N 段會用到」；拍不到的區域可以略過
    test('載入：每個區域的白話說明、用到的段、略過的區域', () async {
      final repo = assetsRepo(
        asset: sampleAsset(hasPhoto: true).copyWith(
          regionHints: {'zone_a': '盤面左邊的方框'},
          regionSegments: {
            'zone_a': [2, 5],
          },
          skippedRegions: ['zone_b'],
        ),
        photo: pngBytes,
      );
      final container = makeContainer(repo);
      await container.read(videoRegionsProvider(ref).notifier).load();
      final state = container.read(videoRegionsProvider(ref));
      expect(state.hints['zone_a'], '盤面左邊的方框');
      expect(state.segments['zone_a'], [2, 5]);
      expect(state.skipped, {'zone_b'});
      // 略過的區域算處理好了；目前選第一個還沒標、也沒略過的
      expect(state.doneCount, 1);
      expect(state.current, 'zone_a');
    });

    test('照片拍不到：略過區域立刻存；可以取消', () async {
      final repo = regionsRepo();
      final container = makeContainer(repo);
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      expect(await notifier.setRegionSkipped('zone_b', true), isTrue);
      expect(repo.updates.single.$3.skippedRegions, ['zone_b']);
      expect(repo.updates.single.$3.regions, isNull);
      var state = container.read(videoRegionsProvider(ref));
      expect(state.skipped, {'zone_b'});
      expect(state.doneCount, 2);
      expect(await notifier.setRegionSkipped('zone_b', false), isTrue);
      expect(repo.updates.last.$3.skippedRegions, isEmpty);
      state = container.read(videoRegionsProvider(ref));
      expect(state.skipped, isEmpty);
    });

    test('文字：第 N 段會用到', () {
      expect(regionSegmentsText([2, 5]), '第 2、5 段會用到');
      expect(regionSegmentsText([]), '目前沒有段用到這個區域');
    });

    test('選區域', () async {
      final container = makeContainer(regionsRepo());
      final notifier = container.read(videoRegionsProvider(ref).notifier);
      await notifier.load();
      notifier.select('zone_a');
      expect(container.read(videoRegionsProvider(ref)).current, 'zone_a');
    });
  });
}

/// HEIC 檔頭（ftyp heic），內容是假的。
Uint8List heicBytes() => Uint8List.fromList([
  0,
  0,
  0,
  0x18,
  ...utf8.encode('ftypheic'),
  0,
  0,
  0,
  0,
  ...utf8.encode('mif1heic'),
  1,
  2,
  3,
]);
