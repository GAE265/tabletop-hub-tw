// 換素材（2026-11-25 永傑決定，最小版）的測試共用資料（自編）。
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../support/fakes.dart';

DraftAsset swapAsset(
  String key,
  String label, {
  String kind = 'flat_photo',
  bool skipped = false,
  List<int>? used,
}) => DraftAsset(
  assetKey: key,
  label: label,
  kind: kind,
  priority: 'must',
  reason: 'r',
  shot: null,
  representative: false,
  regions: const [],
  hasPhoto: true,
  skipped: skipped,
  usedInSegments: used,
);

/// s1：主畫面三張牌（紅牌、牌背、藍牌，不能換）、側欄是圖板（可以換）；s2：主畫面是紅牌（可以換）。
/// 素材另有繪製的骰子、已略過的金幣（都不能拿來換）。
VideoDraft swapDraft({
  int version = 3,
  List<int>? boardUsed = const [1],
}) => VideoDraft(
  videoVersion: version,
  segments: const [
    DraftSegment(
      segmentKey: 's1',
      chapter: 'setup',
      sourcePages: [3],
      beats: [DraftBeat(beatKey: 'b1', narration: '把紅牌放進甲區。', subtitle: '放牌')],
      slots: [
        DraftSlot(
          slot: 'main',
          kind: 'items',
          assetKeys: ['red', 'back', 'blue'],
          swappable: false,
        ),
        DraftSlot(
          slot: 'sidebar',
          kind: 'asset',
          assetKeys: ['board'],
          swappable: true,
        ),
      ],
    ),
    DraftSegment(
      segmentKey: 's2',
      chapter: 'round',
      sourcePages: [6],
      beats: [DraftBeat(beatKey: 'b2', narration: '再看一次紅牌。', subtitle: '紅牌')],
      slots: [
        DraftSlot(
          slot: 'main',
          kind: 'asset',
          assetKeys: ['red'],
          swappable: true,
        ),
      ],
    ),
  ],
  assets: [
    swapAsset('back', '牌背', used: const [1]),
    swapAsset('red', '紅牌', used: const [1, 2]),
    swapAsset('blue', '藍牌', used: const [1]),
    swapAsset('board', '圖板', used: boardUsed),
    swapAsset('dice', '骰子', kind: 'drawn', used: const []),
    swapAsset('coin', '金幣', skipped: true, used: const [1]),
  ],
  coverage: const DraftCoverage(
    status: 'done',
    totalRules: 0,
    issues: [],
    problems: [],
    hints: [],
  ),
  terms: const DraftTerms(status: 'used'),
  pagesStale: false,
);

/// 換 s1 側欄（圖板 → 藍牌）的結果：移除框線 h1 與一個移動，圖板沒有段在用了。
const sidebarSwapResult = SegmentSwapResult(
  segmentKey: 's1',
  slot: 'sidebar',
  oldAssetKey: 'board',
  newAssetKey: 'blue',
  removed: SwapRemoved(
    highlights: ['h1'],
    labels: [],
    cues: [SwapRemovedCue(beatKey: 'b1', action: 'move', target: 'main.c1')],
  ),
  unusedAssets: ['board'],
  videoVersion: 4,
);

FakeVideoStudioRepository swapRepo({VideoDraft? draft}) =>
    FakeVideoStudioRepository(
        projects: [sampleVideoProject()],
        drafts: {'p1': draft ?? swapDraft()},
      )
      ..readiness['p1'] = const VideoReadiness(
        ready: true,
        missingPhotos: [],
        missingRegions: [],
        unsupported: [],
      );
