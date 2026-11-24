// 換素材（2026-11-25 永傑決定；完整版）的 state 與純函式：可以換成哪些素材、換完的提示
// （要重標的區域）、版本衝突、放牌的格子逐張換、新增素材後直接換上；
// 沒有段在用的素材不算進進度、另外列出。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_summary.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_draft_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_segment_swap_state.dart';

import '../../support/fakes.dart';
import 'video_swap_support.dart';

ProviderContainer makeContainer(FakeVideoStudioRepository repo) {
  final container = ProviderContainer(
    overrides: [videoStudioRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}

DraftSlot slotOf(VideoDraft draft, String segment, String slot) => draft
    .segments
    .firstWhere((s) => s.segmentKey == segment)
    .slots
    .firstWhere((s) => s.slot == slot);

Future<(ProviderContainer, VideoDraft)> setUpSwap(
  FakeVideoStudioRepository repo,
) async {
  final container = makeContainer(repo);
  final draft = (await container.read(videoDraftProvider('p1').future))!;
  final sub = container.listen(videoSegmentSwapProvider('p1'), (_, _) {});
  addTearDown(sub.close);
  return (container, draft);
}

void main() {
  group('可以換成哪些素材', () {
    test('不含目前這個、繪製素材、已略過的素材', () {
      final keys = swapCandidates(swapDraft(), 'board').map((a) => a.assetKey);
      expect(keys, ['back', 'red', 'blue']);
    });

    test('換牌時也排除目前那一面的素材', () {
      final keys = swapCandidates(swapDraft(), 'blue').map((a) => a.assetKey);
      expect(keys, ['back', 'red', 'board']);
    });
  });

  group('換完的提示', () {
    test('列出換成什麼、要重標的區域、哪個素材不用再拍', () {
      expect(
        swapNotice(sidebarSwapResult, swapDraft()),
        '已換成「藍牌」。要在新照片上標出：甲區、乙區。「圖板」目前沒有段用到，不用拍',
      );
    });

    test('不用重標：只說換成什麼', () {
      const result = SegmentSwapResult(
        segmentKey: 's2',
        slot: 'main',
        face: 'front',
        oldAssetKey: 'red',
        newAssetKey: 'blue',
        regionsToMark: [],
        unusedAssets: [],
        videoVersion: 4,
      );
      expect(swapNotice(result, swapDraft()), '已換成「藍牌」');
    });

    test('換牌背：說明是牌背', () {
      const result = SegmentSwapResult(
        segmentKey: 's1',
        slot: 'main',
        itemKey: 'c1',
        face: 'back',
        oldAssetKey: 'back',
        newAssetKey: 'blue',
        regionsToMark: [],
        unusedAssets: [],
        videoVersion: 4,
      );
      expect(swapNotice(result, swapDraft()), '牌背已換成「藍牌」');
    });
  });

  group('換素材', () {
    test('送出目前看到的版本；成功後顯示提示，草稿重新讀取', () async {
      final repo = swapRepo()..swapResult = sidebarSwapResult;
      final (container, draft) = await setUpSwap(repo);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: slotOf(draft, 's1', 'sidebar'),
            assetKey: 'blue',
          );

      expect(ok, isTrue);
      final (project, segment, input) = repo.swaps.single;
      expect((project, segment), ('p1', 's1'));
      expect(input.toJson(), {
        'slot': 'sidebar',
        'asset_key': 'blue',
        'face': 'front',
        'video_version': 3,
      });
      final state = container.read(videoSegmentSwapProvider('p1'));
      expect(state.busy, isFalse);
      expect(state.error, isNull);
      expect(state.notice, startsWith('已換成「藍牌」'));
      final reloaded = (await container.read(videoDraftProvider('p1').future))!;
      expect(reloaded.videoVersion, 4);
    });

    test('放牌的格子：送出哪一張與正面或牌背', () async {
      final repo = swapRepo();
      final (container, draft) = await setUpSwap(repo);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: slotOf(draft, 's1', 'main'),
            assetKey: 'blue',
            itemKey: 'c1',
            face: 'back',
          );

      expect(ok, isTrue);
      expect(repo.swaps.single.$3.toJson(), {
        'slot': 'main',
        'asset_key': 'blue',
        'item_key': 'c1',
        'face': 'back',
        'video_version': 3,
      });
    });

    test('版本衝突（409）：顯示後端的說明，草稿重新讀取', () async {
      final repo = swapRepo()
        ..swapError = const ApiException(
          code: 'RULES_VIDEO_CONFLICT',
          message: '草稿已被修改，請重新整理後再換',
          statusCode: 409,
        );
      final (container, draft) = await setUpSwap(repo);
      repo.drafts['p1'] = swapDraft(version: 9);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: slotOf(draft, 's1', 'sidebar'),
            assetKey: 'blue',
          );

      expect(ok, isFalse);
      final state = container.read(videoSegmentSwapProvider('p1'));
      expect(state.error, '草稿已被修改，請重新整理後再換');
      expect(state.notice, isNull);
      final reloaded = (await container.read(videoDraftProvider('p1').future))!;
      expect(reloaded.videoVersion, 9);
    });

    test('其他錯誤：顯示後端的說明', () async {
      final repo = swapRepo()
        ..swapError = const ApiException(
          code: 'RULES_VIDEO_ITEM_NO_BACK',
          message: '這張牌沒有牌背，不能換牌背',
          statusCode: 422,
        );
      final (container, draft) = await setUpSwap(repo);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: slotOf(draft, 's1', 'sidebar'),
            assetKey: 'blue',
          );

      expect(ok, isFalse);
      expect(
        container.read(videoSegmentSwapProvider('p1')).error,
        '這張牌沒有牌背，不能換牌背',
      );
    });
  });

  group('新增素材後直接換上', () {
    test('先新增（用目前版本），再用新增後的版本換上', () async {
      final repo = swapRepo();
      final (container, draft) = await setUpSwap(repo);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .createAndSwap(
            draft: draft,
            segmentKey: 's2',
            slot: slotOf(draft, 's2', 'main'),
            label: '白薔薇',
            shot: '整張牌正面朝上',
          );

      expect(ok, isTrue);
      final created = repo.createdAssets.single;
      expect(created.$1, 'p1');
      expect(created.$2.toJson(), {
        'label': '白薔薇',
        'shot': '整張牌正面朝上',
        'video_version': 3,
      });
      final input = repo.swaps.single.$3;
      expect(input.assetKey, 'custom_1');
      expect(input.videoVersion, 4); // 新增後版本加 1
      expect(
        container.read(videoSegmentSwapProvider('p1')).notice,
        startsWith('已換成「白薔薇」'),
      );
    });

    test('新增失敗（同名）：顯示後端的說明，不換', () async {
      final repo = swapRepo()
        ..createAssetError = const ApiException(
          code: 'RULES_VIDEO_ASSET_LABEL_TAKEN',
          message: '已經有叫「紅牌」的素材，請換一個名稱',
          statusCode: 422,
        );
      final (container, draft) = await setUpSwap(repo);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .createAndSwap(
            draft: draft,
            segmentKey: 's2',
            slot: slotOf(draft, 's2', 'main'),
            label: '紅牌',
          );

      expect(ok, isFalse);
      expect(repo.swaps, isEmpty);
      expect(
        container.read(videoSegmentSwapProvider('p1')).error,
        '已經有叫「紅牌」的素材，請換一個名稱',
      );
    });
  });

  group('沒有段在用的素材', () {
    test('不算進進度的總數；另外列出', () {
      final draft = swapDraft(boardUsed: const []);
      expect(
        isUnusedAsset(draft.assets.firstWhere((a) => a.assetKey == 'board')),
        isTrue,
      );
      expect(unusedAssets(draft).map((a) => a.assetKey), ['board', 'dice']);
      final progress = assetsProgress(draft, null);
      expect(progress.total, 4);
    });

    test('舊的回應沒有 used_in_segments：照原本的方式算（不算沒用到）', () {
      final asset = swapAsset('x', '舊素材');
      expect(asset.usedInSegments, isNull);
      expect(isUnusedAsset(asset), isFalse);
    });
  });
}
