import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 專案的草稿；還沒有草稿時是 null。草稿工作完成時會重新讀取。
final videoDraftProvider = FutureProvider.family<VideoDraft?, String>(
  (ref, projectId) =>
      ref.read(videoStudioRepositoryProvider).getDraft(projectId),
  retry: (_, _) => null,
);

/// 店員逐句勾選「已檢查」的字幕（句子的 key）。只存在畫面上，不存後端（design.md D12）。
class SubtitleChecksNotifier extends Notifier<Set<String>> {
  SubtitleChecksNotifier(this.projectId);

  final String projectId;

  @override
  Set<String> build() => const {};

  void toggle(String beatKey) => state = state.contains(beatKey)
      ? ({...state}..remove(beatKey))
      : {...state, beatKey};
}

final subtitleChecksProvider = NotifierProvider.autoDispose
    .family<SubtitleChecksNotifier, Set<String>, String>(
      SubtitleChecksNotifier.new,
    );

/// 已檢查幾句、共幾句。
(int, int) checkedCount(Set<String> checks, VideoDraft draft) {
  final keys = [
    for (final segment in draft.segments)
      for (final beat in segment.beats) beat.beatKey,
  ];
  return (keys.where(checks.contains).length, keys.length);
}
