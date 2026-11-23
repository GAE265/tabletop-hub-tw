import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 專案的草稿；還沒有草稿時是 null。草稿工作完成時會重新讀取。
final videoDraftProvider = FutureProvider.family<VideoDraft?, String>(
  (ref, projectId) =>
      ref.read(videoStudioRepositoryProvider).getDraft(projectId),
  retry: (_, _) => null,
);

/// 三格的 key 與名稱，依影片的順序（和後端 video_scope.SLOTS 一致）。
const videoSlots = [('setup', '開局'), ('round', '走完一輪'), ('win', '獲勝方式')];

class DraftSlotSummary {
  const DraftSlotSummary(this.key, this.title, this.segments, this.beats);

  final String key;
  final String title;
  final int segments;
  final int beats;
}

class DraftSummary {
  const DraftSummary(this.slots, this.assets, this.skippableAssets);

  final List<DraftSlotSummary> slots;

  /// 沒有略過的素材數。
  final int assets;

  /// 其中可以略過的（後端程式判斷，不看 AI 標的 priority）。
  final int skippableAssets;
}

/// 草稿頁只顯示結果摘要（D17：不擋流程）：三格各幾段幾句、素材幾個與其中可略過幾個。
DraftSummary draftSummary(VideoDraft draft) => DraftSummary(
  [
    for (final (key, title) in videoSlots)
      DraftSlotSummary(
        key,
        title,
        draft.segments.where((s) => s.chapter == key).length,
        draft.segments
            .where((s) => s.chapter == key)
            .fold(0, (sum, s) => sum + s.beats.length),
      ),
  ],
  draft.assets.where((a) => !a.skipped).length,
  draft.assets.where((a) => !a.skipped && a.skippable).length,
);

/// 給店員看的素材名稱：中文名稱；舊的草稿沒有時用 reason（不顯示 asset_key 這類內部代號）。
String assetDisplayName(DraftAsset asset) =>
    (asset.label?.isNotEmpty ?? false) ? asset.label! : asset.reason;
