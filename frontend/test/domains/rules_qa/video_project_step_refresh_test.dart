// 專案總覽的步驟要跟著素材的變動更新（手機實測發現：拍完、略過素材後，總覽還停在「生成草稿」）。
// 每個會改到素材的動作成功後，都要重新讀取專案（videoProjectProvider），步驟由後端算。
import 'package:flutter/painting.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_summary.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_draft_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_projects_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_segment_swap_state.dart';

import '../../support/fakes.dart';
import 'video_assets_support.dart';
import 'video_swap_support.dart';

const asset = (projectId: 'p1', assetKey: 'board');

/// 先讀一次專案（總覽頁看到的步驟），再讓後端的步驟變成 [after]。
Future<ProviderContainer> watchStep(
  FakeVideoStudioRepository repo, {
  String after = 'render',
  FakeImagePicker? picker,
}) async {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      imagePickerProvider.overrideWithValue(picker ?? FakeImagePicker()),
    ],
  );
  addTearDown(container.dispose);
  final sub = container.listen(videoProjectProvider('p1'), (_, _) {});
  addTearDown(sub.close);
  expect(
    (await container.read(videoProjectProvider('p1').future)).step,
    'draft',
  );
  repo.projects = [sampleVideoProject(step: after)];
  return container;
}

Future<String> stepOf(ProviderContainer container) async =>
    (await container.read(videoProjectProvider('p1').future)).step;

void main() {
  group('素材頁的動作之後，總覽的步驟重新讀取', () {
    test('拍照上傳', () async {
      final picker = FakeImagePicker()..images = [picked()];
      final container = await watchStep(
        assetsRepo(),
        after: 'assets',
        picker: picker,
      );
      final notifier = container.read(videoAssetProvider(asset).notifier);
      await notifier.load();
      await notifier.pickAndUpload();
      expect(await stepOf(container), 'assets');
    });

    test('旋轉照片', () async {
      final container = await watchStep(
        assetsRepo(asset: sampleAsset(hasPhoto: true), photo: pngBytes),
      );
      final notifier = container.read(videoAssetProvider(asset).notifier);
      await notifier.load();
      await notifier.rotate();
      expect(await stepOf(container), 'render');
    });

    test('略過素材', () async {
      final container = await watchStep(assetsRepo());
      final notifier = container.read(videoAssetProvider(asset).notifier);
      await notifier.load();
      expect(await notifier.setSkipped(true), isTrue);
      expect(await stepOf(container), 'render');
    });

    test('在清單上略過素材', () async {
      final container = await watchStep(assetsRepo());
      expect(
        await container
            .read(videoAssetListProvider('p1').notifier)
            .skip('board'),
        isTrue,
      );
      expect(await stepOf(container), 'render');
    });
  });

  group('標區域之後，總覽的步驟重新讀取', () {
    FakeVideoStudioRepository regionsRepo() => assetsRepo(
      asset: sampleAsset(
        hasPhoto: true,
        regions: const {
          'zone_a': [0.1, 0.1, 0.2, 0.2],
          'zone_b': null,
        },
      ),
      photo: pngBytes,
    );

    test('儲存區域', () async {
      final container = await watchStep(regionsRepo());
      final notifier = container.read(videoRegionsProvider(asset).notifier);
      await notifier.load();
      notifier.setBox('zone_b', const Rect.fromLTWH(0.5, 0.25, 0.25, 0.5));
      expect(await notifier.save(), isTrue);
      expect(await stepOf(container), 'render');
    });

    test('略過區域', () async {
      final container = await watchStep(regionsRepo());
      final notifier = container.read(videoRegionsProvider(asset).notifier);
      await notifier.load();
      expect(await notifier.setRegionSkipped('zone_b', true), isTrue);
      expect(await stepOf(container), 'render');
    });
  });

  test('換素材之後，總覽的步驟重新讀取', () async {
    final repo = swapRepo()..swapResult = sidebarSwapResult;
    final container = await watchStep(repo, after: 'assets');
    final draft = (await container.read(videoDraftProvider('p1').future))!;
    final sub = container.listen(videoSegmentSwapProvider('p1'), (_, _) {});
    addTearDown(sub.close);
    final slot = draft.segments
        .firstWhere((s) => s.segmentKey == 's1')
        .slots
        .firstWhere((s) => s.slot == 'sidebar');
    final ok = await container
        .read(videoSegmentSwapProvider('p1').notifier)
        .swap(draft: draft, segmentKey: 's1', slot: slot, assetKey: 'blue');
    expect(ok, isTrue);
    expect(await stepOf(container), 'assets');
  });
}
