import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_assets_state.dart';
import 'video_draft_state.dart';
import 'video_job_state.dart';
import 'video_projects_state.dart';
import 'video_render_state.dart';

/// 用一句話修改（add-rules-video-mobile MR 12）：店員寫下要怎麼改 → AI 算出提案（不寫入草稿）→
/// 店員看過再套用。版型做不到時選一個替代做法；不確定改哪一段時選一段再重新送出。
/// 套用後不做規則涵蓋檢查（2026-11-26 永傑決定，之後再加）。

/// 修改要求的字數上限（和後端 REVISION_REQUEST_MAX_CHARS 一致）。
const revisionRequestMaxChars = 200;

/// 欄位分類（後端 video_revision.CATEGORIES）給店員看的說法。
String revisionCategoryName(String category) => switch (category) {
  'narration' => '旁白',
  'subtitle' => '字幕',
  'keywords' => '重點詞',
  'cues' => '動作',
  'beats' => '句子（新增或刪除）',
  'slots' => '素材',
  'highlights' => '框線',
  'labels' => '標籤',
  'timing' => '時間',
  'template' => '版型',
  'transition_in' => '轉場',
  'source_pages' => '出處頁',
  _ => category,
};

/// 「改了：框線、字幕」這類說明。
String revisionCategories(List<String> categories) =>
    categories.map(revisionCategoryName).join('、');

/// 選段的選項：第 N 段加上第一句旁白（不顯示段代號這類內部代號）。
String revisionSegmentOption(VideoDraft draft, int index) {
  final segment = draft.segments[index];
  final first = segment.beats.isEmpty ? '' : segment.beats.first.narration;
  return ['第 ${index + 1} 段', if (first.isNotEmpty) first].join('：');
}

/// 套用後的提示：改了哪幾段，影片要重新產生才會更新。
String revisionAppliedNotice(VideoRevision revision) {
  final segments = revision.appliedAlternative == null
      ? revision.segments
      : revision.alternatives
            .firstWhere(
              (a) => a.number == revision.appliedAlternative,
              orElse: () => const RevisionAlternative(
                number: 0,
                title: '',
                description: '',
              ),
            )
            .segments;
  final numbers = segments.map((s) => '第 ${s.segmentNumber} 段').join('、');
  return [numbers.isEmpty ? '已套用' : '已套用到$numbers', '影片要重新產生才會更新'].join('。');
}

class VideoRevisionState {
  const VideoRevisionState({this.revision, this.busy = false, this.error});

  /// 最近一次修改（AI 在算、算完或已套用）；還沒送出時是 null。
  final VideoRevision? revision;

  /// 送出或套用中。
  final bool busy;

  /// 送出、查詢或套用時後端回的說明（AI 沒算成的原因在 `revision.error`）。
  final String? error;

  /// AI 還在算。
  bool get thinking => revision?.active ?? false;
}

class VideoRevisionNotifier extends Notifier<VideoRevisionState> {
  VideoRevisionNotifier(this.projectId);

  final String projectId;
  Future<void>? _polling;

  /// 目前這一輪查詢結束（測試用來等待）。
  Future<void> get finished => _polling ?? Future.value();

  VideoStudioRepository get _repo => ref.read(videoStudioRepositoryProvider);

  @override
  VideoRevisionState build() => const VideoRevisionState();

  /// 用店員看到的草稿版本送出；[segmentKey] 給定時只改那一段。成功後每隔一段時間查一次，直到算完。
  Future<bool> submit({
    required VideoDraft draft,
    required String request,
    String? segmentKey,
  }) async {
    final text = request.trim();
    if (state.busy || state.thinking || text.isEmpty) return false;
    state = VideoRevisionState(revision: state.revision, busy: true);
    try {
      final revision = await _repo.createRevision(
        projectId,
        VideoRevisionCreate(
          request: text,
          segmentKey: segmentKey,
          videoVersion: draft.videoVersion,
        ),
      );
      if (!ref.mounted) return true;
      state = VideoRevisionState(revision: revision);
      _poll(revision.id);
      return true;
    } on ApiException catch (error) {
      if (!ref.mounted) return false;
      state = VideoRevisionState(
        revision: state.revision,
        error: error.message,
      );
      // 版本衝突：草稿已經變了，重新讀取
      if (error.code == 'RULES_VIDEO_CONFLICT') {
        ref.invalidate(videoDraftProvider(projectId));
      }
      return false;
    }
  }

  /// 不確定改哪一段時：用同一句修改要求，只改店員選的那一段，重新送出。
  Future<bool> chooseSegment({
    required VideoDraft draft,
    required RevisionCandidate candidate,
  }) {
    final request = state.revision?.request ?? '';
    return submit(
      draft: draft,
      request: request,
      segmentKey: candidate.segmentKey,
    );
  }

  /// 套用提案（[alternative] 是 null）或選的替代做法。成功後重新讀取草稿、還缺什麼與專案。
  Future<bool> apply({required VideoDraft draft, int? alternative}) async {
    final revision = state.revision;
    if (revision == null || state.busy) return false;
    state = VideoRevisionState(revision: revision, busy: true);
    try {
      final applied = await _repo.applyRevision(
        projectId,
        revision.id,
        VideoRevisionApply(
          alternative: alternative,
          videoVersion: draft.videoVersion,
        ),
      );
      if (!ref.mounted) return true;
      state = VideoRevisionState(revision: applied);
      _refresh();
      return true;
    } on ApiException catch (error) {
      if (!ref.mounted) return false;
      state = VideoRevisionState(revision: revision, error: error.message);
      // 草稿被改過（或已經套用過）：重新讀取，讓店員看到最新的
      ref.invalidate(videoDraftProvider(projectId));
      return false;
    }
  }

  /// 再提一個修改：清掉上一次的結果。
  void reset() {
    if (state.thinking || state.busy) return;
    state = const VideoRevisionState();
  }

  void _refresh() {
    ref
      ..invalidate(videoDraftProvider(projectId))
      ..invalidate(videoReadinessProvider(projectId))
      ..invalidate(videoProjectsProvider)
      ..invalidate(videoProjectProvider(projectId))
      ..invalidate(videoRenderProvider(projectId));
  }

  void _poll(String revisionId) {
    _polling ??= _loop(revisionId).whenComplete(() => _polling = null);
  }

  Future<void> _loop(String revisionId) async {
    final interval = ref.read(videoJobPollIntervalProvider);
    while (true) {
      await Future<void>.delayed(interval);
      if (!ref.mounted) return;
      try {
        final revision = await _repo.getRevision(projectId, revisionId);
        if (!ref.mounted) return;
        state = VideoRevisionState(revision: revision);
        if (!revision.active) return;
      } on ApiException catch (error) {
        if (ref.mounted) {
          state = VideoRevisionState(
            revision: state.revision,
            error: error.message,
          );
        }
        return;
      }
    }
  }
}

/// 留在記憶體裡：離開修改頁時 AI 照樣算，回來看得到結果。
final videoRevisionProvider =
    NotifierProvider.family<VideoRevisionNotifier, VideoRevisionState, String>(
      VideoRevisionNotifier.new,
    );
