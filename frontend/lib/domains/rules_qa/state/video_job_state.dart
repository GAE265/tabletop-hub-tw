import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_draft_state.dart';
import 'video_projects_state.dart';

/// 查詢工作進度的間隔（測試換成 0）。
final videoJobPollIntervalProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 2),
);

class VideoJobState {
  const VideoJobState({this.job, this.error});

  /// 最近一個工作（進行中或剛結束）。
  final VideoJob? job;

  /// 建立工作或查詢時的錯誤（工作本身的失敗原因在 `job.error`）。
  final String? error;

  bool get running => job?.active ?? false;
}

/// 專案的工作進度：建立草稿工作、每隔一段時間查一次，直到結束（design.md D12）。
/// 留在記憶體裡，離開頁面也會繼續查；回到專案時用 [resume] 接上最近的工作。
class VideoJobNotifier extends Notifier<VideoJobState> {
  VideoJobNotifier(this.projectId);

  final String projectId;
  Future<void>? _polling;

  /// 目前這一輪查詢結束（測試用來等待）。
  Future<void> get finished => _polling ?? Future.value();

  @override
  VideoJobState build() => const VideoJobState();

  VideoStudioRepository get _repo => ref.read(videoStudioRepositoryProvider);

  Future<void> startDraft() async {
    try {
      final job = await _repo.startDraft(projectId);
      state = VideoJobState(job: job);
      _poll(job.id);
    } on ApiException catch (error) {
      final running = error.details['job_id'];
      if (error.code == 'RULES_VIDEO_JOB_RUNNING' && running is String) {
        // 已有進行中的工作：接上它
        _poll(running);
        return;
      }
      state = VideoJobState(job: state.job, error: error.message);
    }
  }

  /// 回到專案時：最近的工作還在進行就接著查，已結束就只顯示結果。
  Future<void> resume() async {
    if (_polling != null) return;
    try {
      final job = await _repo.latestJob(projectId);
      state = VideoJobState(job: job);
      if (job != null && job.active) _poll(job.id);
    } on ApiException catch (error) {
      state = VideoJobState(job: state.job, error: error.message);
    }
  }

  void _poll(String jobId) {
    _polling ??= _loop(jobId).whenComplete(() => _polling = null);
  }

  Future<void> _loop(String jobId) async {
    final interval = ref.read(videoJobPollIntervalProvider);
    while (true) {
      await Future<void>.delayed(interval);
      try {
        final job = await _repo.getJob(projectId, jobId);
        state = VideoJobState(job: job);
        if (job.active) continue;
        if (job.status == VideoJobStatus.succeeded) {
          ref
            ..invalidate(videoDraftProvider(projectId))
            ..invalidate(videoProjectsProvider);
        }
        return;
      } on ApiException catch (error) {
        state = VideoJobState(job: state.job, error: error.message);
        return;
      }
    }
  }
}

final videoJobProvider =
    NotifierProvider.family<VideoJobNotifier, VideoJobState, String>(
      VideoJobNotifier.new,
    );
