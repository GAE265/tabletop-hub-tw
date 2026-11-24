// 換素材（2026-11-25 永傑決定，最小版）的 state 與純函式：可以換成哪些素材、換完的提示、
// 版本衝突；沒有段在用的素材不算進進度、另外列出。
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

DraftSlot sidebarOf(VideoDraft draft) =>
    draft.segments.first.slots.firstWhere((s) => s.slot == 'sidebar');

void main() {
  group('可以換成哪些素材', () {
    test('不含目前這個、繪製素材、已略過的素材', () {
      final draft = swapDraft();
      final keys = swapCandidates(
        draft,
        sidebarOf(draft),
      ).map((a) => a.assetKey);
      expect(keys, ['back', 'red', 'blue']);
    });
  });

  group('換完的提示', () {
    test('列出換成什麼、移除了什麼、哪個素材不用再拍', () {
      expect(
        swapNotice(sidebarSwapResult, swapDraft()),
        '已換成「藍牌」。已移除：框線 1 個、動作 1 個。「圖板」目前沒有段用到，不用拍',
      );
    });

    test('沒有移除任何東西：只說換成什麼', () {
      const result = SegmentSwapResult(
        segmentKey: 's2',
        slot: 'main',
        oldAssetKey: 'red',
        newAssetKey: 'blue',
        removed: SwapRemoved(highlights: [], labels: [], cues: []),
        unusedAssets: [],
        videoVersion: 4,
      );
      expect(swapNotice(result, swapDraft()), '已換成「藍牌」');
    });
  });

  group('換素材', () {
    test('送出目前看到的版本；成功後顯示提示，草稿重新讀取', () async {
      final repo = swapRepo()..swapResult = sidebarSwapResult;
      final container = makeContainer(repo);
      final draft = (await container.read(videoDraftProvider('p1').future))!;
      final sub = container.listen(videoSegmentSwapProvider('p1'), (_, _) {});
      addTearDown(sub.close);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: sidebarOf(draft),
            assetKey: 'blue',
          );

      expect(ok, isTrue);
      final (project, segment, input) = repo.swaps.single;
      expect((project, segment), ('p1', 's1'));
      expect(input.toJson(), {
        'slot': 'sidebar',
        'asset_key': 'blue',
        'video_version': 3,
      });
      final state = container.read(videoSegmentSwapProvider('p1'));
      expect(state.busy, isFalse);
      expect(state.error, isNull);
      expect(state.notice, startsWith('已換成「藍牌」'));
      final reloaded = (await container.read(videoDraftProvider('p1').future))!;
      expect(reloaded.videoVersion, 4);
    });

    test('版本衝突（409）：顯示後端的說明，草稿重新讀取', () async {
      final repo = swapRepo()
        ..swapError = const ApiException(
          code: 'RULES_VIDEO_CONFLICT',
          message: '草稿已被修改，請重新整理後再換',
          statusCode: 409,
        );
      final container = makeContainer(repo);
      final draft = (await container.read(videoDraftProvider('p1').future))!;
      final sub = container.listen(videoSegmentSwapProvider('p1'), (_, _) {});
      addTearDown(sub.close);
      repo.drafts['p1'] = swapDraft(version: 9);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: sidebarOf(draft),
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
          code: 'RULES_VIDEO_SWAP_UNSUPPORTED',
          message: '這一段目前不支援換素材',
          statusCode: 422,
        );
      final container = makeContainer(repo);
      final draft = (await container.read(videoDraftProvider('p1').future))!;
      final sub = container.listen(videoSegmentSwapProvider('p1'), (_, _) {});
      addTearDown(sub.close);

      final ok = await container
          .read(videoSegmentSwapProvider('p1').notifier)
          .swap(
            draft: draft,
            segmentKey: 's1',
            slot: sidebarOf(draft),
            assetKey: 'blue',
          );

      expect(ok, isFalse);
      expect(
        container.read(videoSegmentSwapProvider('p1')).error,
        '這一段目前不支援換素材',
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
      // 6 個素材扣掉沒用到的圖板與骰子：4 個；金幣已略過也算完成
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
