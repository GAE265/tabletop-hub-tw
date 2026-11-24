import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_assets_state.dart';
import 'video_draft_state.dart';

/// 換素材（2026-11-25 永傑決定，最小版）：只有單一素材的格子可以換，只能換成清單裡可以用的素材。

/// 格子名稱給店員看的說法。
String slotDisplayName(String slot) => switch (slot) {
  'main' => '主畫面',
  'sidebar' => '側欄',
  _ => slot,
};

/// 這一格可以換成哪些素材：不含目前用的、繪製素材、已略過的。
List<DraftAsset> swapCandidates(VideoDraft draft, DraftSlot slot) => [
  for (final a in draft.assets)
    if (!slot.assetKeys.contains(a.assetKey) && a.kind != 'drawn' && !a.skipped)
      a,
];

/// 換完的提示：換成什麼、移除了什麼（框線、標籤、動作各幾個）、哪些素材不用再拍。
String swapNotice(SegmentSwapResult result, VideoDraft draft) {
  final names = {for (final a in draft.assets) a.assetKey: assetDisplayName(a)};
  String name(String key) => names[key] ?? key;
  final removed = [
    if (result.removed.highlights.isNotEmpty)
      '框線 ${result.removed.highlights.length} 個',
    if (result.removed.labels.isNotEmpty)
      '標籤 ${result.removed.labels.length} 個',
    if (result.removed.cues.isNotEmpty) '動作 ${result.removed.cues.length} 個',
  ];
  return [
    '已換成「${name(result.newAssetKey)}」',
    if (removed.isNotEmpty) '已移除：${removed.join('、')}',
    if (result.unusedAssets.isNotEmpty)
      '${result.unusedAssets.map((k) => '「${name(k)}」').join('、')}目前沒有段用到，不用拍',
  ].join('。');
}

class VideoSegmentSwapState {
  const VideoSegmentSwapState({this.busy = false, this.notice, this.error});

  final bool busy;

  /// 換完的提示（見 [swapNotice]）。
  final String? notice;

  /// 後端回的說明（例如版本衝突、這一段不支援）。
  final String? error;
}

class VideoSegmentSwapNotifier extends Notifier<VideoSegmentSwapState> {
  VideoSegmentSwapNotifier(this.projectId);

  final String projectId;

  @override
  VideoSegmentSwapState build() => const VideoSegmentSwapState();

  /// 用店員看到的草稿版本送出；成功後重新讀取草稿與「還缺什麼」。
  /// 版本衝突時也重新讀取草稿，讓店員看到最新的再換。
  Future<bool> swap({
    required VideoDraft draft,
    required String segmentKey,
    required DraftSlot slot,
    required String assetKey,
  }) async {
    if (state.busy) return false;
    state = const VideoSegmentSwapState(busy: true);
    try {
      final result = await ref
          .read(videoStudioRepositoryProvider)
          .swapSegmentAsset(
            projectId,
            segmentKey,
            SegmentSwapInput(
              slot: slot.slot,
              assetKey: assetKey,
              videoVersion: draft.videoVersion,
            ),
          );
      if (!ref.mounted) return true;
      state = VideoSegmentSwapState(notice: swapNotice(result, draft));
      ref.invalidate(videoDraftProvider(projectId));
      ref.invalidate(videoReadinessProvider(projectId));
      return true;
    } on ApiException catch (error) {
      if (!ref.mounted) return false;
      state = VideoSegmentSwapState(error: error.message);
      if (error.code == 'RULES_VIDEO_CONFLICT') {
        ref.invalidate(videoDraftProvider(projectId));
      }
      return false;
    }
  }
}

final videoSegmentSwapProvider = NotifierProvider.autoDispose
    .family<VideoSegmentSwapNotifier, VideoSegmentSwapState, String>(
      VideoSegmentSwapNotifier.new,
    );
