import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_assets_state.dart';
import 'video_draft_state.dart';

/// 素材清單上方的完成進度。
class VideoAssetsProgress {
  const VideoAssetsProgress({
    required this.total,
    required this.done,
    required this.skipped,
  });

  /// 全部素材數。
  final int total;

  /// 完成的素材數：已拍且區域都標好，或已略過。
  final int done;

  /// 已略過的素材數（包含在 [done] 裡）。
  final int skipped;

  /// 還沒完成的素材數。
  int get pending => total - done;

  /// 完成的百分比（四捨五入）；沒有素材時是 100。
  int get percent => total == 0 ? 100 : (done * 100 / total).round();
}

/// 依素材清單與還缺什麼算完成進度；[readiness] 還沒讀到時只看有沒有照片或略過。
VideoAssetsProgress assetsProgress(
  VideoDraft draft,
  VideoReadiness? readiness,
) {
  final pending = readiness == null ? null : _pendingKeys(readiness);
  var done = 0;
  var skipped = 0;
  for (final a in draft.assets) {
    if (a.skipped) {
      skipped++;
      done++;
    } else if (a.hasPhoto && !(pending?.contains(a.assetKey) ?? false)) {
      done++;
    }
  }
  return VideoAssetsProgress(
    total: draft.assets.length,
    done: done,
    skipped: skipped,
  );
}

Set<String> _pendingKeys(VideoReadiness readiness) => {
  for (final p in readiness.missingPhotos) p.assetKey,
  for (final r in readiness.missingRegions) r.assetKey,
};

/// 還缺照片或區域的素材，依素材清單的順序。
List<String> pendingAssetKeys(VideoDraft draft, VideoReadiness readiness) {
  final pending = _pendingKeys(readiness);
  return [
    for (final a in draft.assets)
      if (pending.contains(a.assetKey)) a.assetKey,
  ];
}

/// 每一格（開局擺放、走完一輪、獲勝方式）有幾段；舊的草稿沒有標格時是空的。
List<(String, int)> chapterSegmentCounts(VideoDraft draft) {
  const chapters = [('setup', '開局擺放'), ('round', '走完一輪'), ('win', '獲勝方式')];
  final counts = <String, int>{};
  for (final s in draft.segments) {
    counts[s.chapter] = (counts[s.chapter] ?? 0) + 1;
  }
  if (!chapters.any((c) => counts.containsKey(c.$1))) return const [];
  return [for (final (key, label) in chapters) (label, counts[key] ?? 0)];
}

/// 素材清單上的操作狀態。
class VideoAssetListState {
  const VideoAssetListState({this.busyKey, this.error});

  /// 正在略過的素材；沒有時是 null。
  final String? busyKey;

  /// 上一次略過失敗的原因（給店員看）。
  final String? error;
}

/// 素材清單上直接略過可以略過的素材（不用先打開素材頁）。
class VideoAssetListNotifier extends Notifier<VideoAssetListState> {
  VideoAssetListNotifier(this.projectId);

  final String projectId;

  @override
  VideoAssetListState build() => const VideoAssetListState();

  /// 略過 [assetKey]；成功回傳 true，並重新讀素材清單與還缺什麼。
  Future<bool> skip(String assetKey) async {
    state = VideoAssetListState(busyKey: assetKey);
    try {
      await ref
          .read(videoStudioRepositoryProvider)
          .updateAsset(
            projectId,
            assetKey,
            const VideoAssetUpdate(skipped: true),
          );
      if (!ref.mounted) return true;
      state = const VideoAssetListState();
      ref
        ..invalidate(videoReadinessProvider(projectId))
        ..invalidate(videoDraftProvider(projectId))
        ..invalidate(
          videoAssetProvider((projectId: projectId, assetKey: assetKey)),
        );
      return true;
    } on ApiException catch (error) {
      if (ref.mounted) state = VideoAssetListState(error: error.message);
      return false;
    }
  }
}

final videoAssetListProvider =
    NotifierProvider.family<
      VideoAssetListNotifier,
      VideoAssetListState,
      String
    >(VideoAssetListNotifier.new);
