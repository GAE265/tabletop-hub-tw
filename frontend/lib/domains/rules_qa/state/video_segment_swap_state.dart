import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_assets_state.dart';
import 'video_draft_state.dart';
import 'video_projects_state.dart';

/// 換素材（2026-11-25 永傑決定；完整版）：單一素材的格子、放牌的格子（逐張換正面或牌背）都可以換，
/// 只能換成清單裡可以用的素材；正確的素材不在清單裡時可以先新增再換上。
/// 框線、標籤、動作都保留，區域沿用到新素材，請店員在新照片上重標。

/// 格子名稱給店員看的說法。
String slotDisplayName(String slot) => switch (slot) {
  'main' => '主畫面',
  'sidebar' => '側欄',
  _ => slot,
};

/// 可以換成哪些素材：不含目前用的那一個、繪製素材、已略過的。
List<DraftAsset> swapCandidates(VideoDraft draft, String currentAssetKey) => [
  for (final a in draft.assets)
    if (a.assetKey != currentAssetKey && a.kind != 'drawn' && !a.skipped) a,
];

/// 換完的提示：換成什麼、要在新照片上標出哪些區域、哪些素材不用再拍。
/// [extraNames] 給剛新增、草稿裡還沒有的素材名稱。
String swapNotice(
  SegmentSwapResult result,
  VideoDraft draft, {
  Map<String, String> extraNames = const {},
}) {
  final names = {
    for (final a in draft.assets) a.assetKey: assetDisplayName(a),
    ...extraNames,
  };
  String name(String key) => names[key] ?? key;
  return [
    '${result.face == 'back' ? '牌背已換成' : '已換成'}「${name(result.newAssetKey)}」',
    if (result.regionsToMark.isNotEmpty)
      '要在新照片上標出：${result.regionsToMark.join('、')}',
    if (result.unusedAssets.isNotEmpty)
      '${result.unusedAssets.map((k) => '「${name(k)}」').join('、')}目前沒有段用到，不用拍',
  ].join('。');
}

class VideoSegmentSwapState {
  const VideoSegmentSwapState({this.busy = false, this.notice, this.error});

  final bool busy;

  /// 換完的提示（見 [swapNotice]）。
  final String? notice;

  /// 後端回的說明（例如版本衝突、同名素材）。
  final String? error;
}

class VideoSegmentSwapNotifier extends Notifier<VideoSegmentSwapState> {
  VideoSegmentSwapNotifier(this.projectId);

  final String projectId;

  VideoStudioRepository get _repo => ref.read(videoStudioRepositoryProvider);

  @override
  VideoSegmentSwapState build() => const VideoSegmentSwapState();

  /// 用店員看到的草稿版本送出；成功後重新讀取草稿與「還缺什麼」。
  /// 放牌的格子給 [itemKey] 與 [face]。版本衝突時也重新讀取草稿，讓店員看到最新的再換。
  Future<bool> swap({
    required VideoDraft draft,
    required String segmentKey,
    required DraftSlot slot,
    required String assetKey,
    String? itemKey,
    String face = 'front',
  }) async {
    if (state.busy) return false;
    state = const VideoSegmentSwapState(busy: true);
    return _run(
      () => _swap(
        draft.videoVersion,
        segmentKey,
        slot,
        assetKey,
        itemKey,
        face,
        draft,
        const {},
      ),
    );
  }

  /// 先新增素材（用店員看到的版本），再用新增後的版本換上去。新增失敗就不換。
  Future<bool> createAndSwap({
    required VideoDraft draft,
    required String segmentKey,
    required DraftSlot slot,
    required String label,
    String? shot,
    String? itemKey,
    String face = 'front',
  }) async {
    if (state.busy) return false;
    state = const VideoSegmentSwapState(busy: true);
    return _run(() async {
      final asset = await _repo.createAsset(
        projectId,
        VideoAssetCreate(
          label: label.trim(),
          shot: (shot?.trim().isEmpty ?? true) ? null : shot!.trim(),
          videoVersion: draft.videoVersion,
        ),
      );
      await _swap(
        asset.videoVersion,
        segmentKey,
        slot,
        asset.assetKey,
        itemKey,
        face,
        draft,
        {asset.assetKey: label.trim()},
      );
    });
  }

  Future<void> _swap(
    int version,
    String segmentKey,
    DraftSlot slot,
    String assetKey,
    String? itemKey,
    String face,
    VideoDraft draft,
    Map<String, String> extraNames,
  ) async {
    final result = await _repo.swapSegmentAsset(
      projectId,
      segmentKey,
      SegmentSwapInput(
        slot: slot.slot,
        assetKey: assetKey,
        itemKey: itemKey,
        face: face,
        videoVersion: version,
      ),
    );
    if (!ref.mounted) return;
    state = VideoSegmentSwapState(
      notice: swapNotice(result, draft, extraNames: extraNames),
    );
  }

  Future<bool> _run(Future<void> Function() action) async {
    try {
      await action();
    } on ApiException catch (error) {
      if (!ref.mounted) return false;
      state = VideoSegmentSwapState(error: error.message);
      // 版本衝突，或新增成功後換失敗：草稿已經變了，重新讀取
      ref.invalidate(videoDraftProvider(projectId));
      ref.invalidate(videoReadinessProvider(projectId));
      ref.invalidate(videoProjectProvider(projectId));
      return false;
    }
    if (!ref.mounted) return true;
    ref.invalidate(videoDraftProvider(projectId));
    ref.invalidate(videoReadinessProvider(projectId));
    ref.invalidate(videoProjectProvider(projectId));
    return true;
  }
}

final videoSegmentSwapProvider = NotifierProvider.autoDispose
    .family<VideoSegmentSwapNotifier, VideoSegmentSwapState, String>(
      VideoSegmentSwapNotifier.new,
    );
