import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/platform/image_picker.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_job_state.dart';
import 'video_projects_state.dart';

/// 規則書頁的狀態（店員拍規則書，2026-11-22 永傑決定）。
class VideoRulebookState {
  const VideoRulebookState({
    this.rulebook,
    this.loading = false,
    this.busy = false,
    this.progress,
    this.error,
  });

  final Rulebook? rulebook;
  final bool loading;

  /// 上傳、刪除或開始中（按鈕停用）。
  final bool busy;

  /// 上傳時的進度文字，例如「上傳中 2／5」。
  final String? progress;
  final String? error;

  List<RulebookPhoto> get photos => rulebook?.photos ?? const [];

  /// 有太模糊、要重拍的照片。
  bool get hasBlurry => photos.any((p) => p.quality == 'bad');

  bool get canStart => photos.isNotEmpty && !hasBlurry && !busy && !loading;

  VideoRulebookState copyWith({
    Rulebook? rulebook,
    bool? loading,
    bool? busy,
    String? progress,
    bool clearProgress = false,
    String? error,
    bool clearError = false,
  }) => VideoRulebookState(
    rulebook: rulebook ?? this.rulebook,
    loading: loading ?? this.loading,
    busy: busy ?? this.busy,
    progress: clearProgress ? null : progress ?? this.progress,
    error: clearError ? null : error ?? this.error,
  );
}

/// 拍規則書：依頁的順序上傳照片、刪掉拍壞的、讀取規則書並產生草稿。
/// 讀取在草稿工作裡做（後端先切塊讀照片、加圖說，再分類與產生草稿）。
class VideoRulebookNotifier extends Notifier<VideoRulebookState> {
  VideoRulebookNotifier(this.projectId);

  final String projectId;

  VideoStudioRepository get _repo => ref.read(videoStudioRepositoryProvider);

  @override
  VideoRulebookState build() => const VideoRulebookState(loading: true);

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final rulebook = await _repo.getRulebook(projectId);
      if (!ref.mounted) return;
      state = state.copyWith(rulebook: rulebook, loading: false);
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(loading: false, error: error.message);
      }
    }
  }

  /// 選圖（可以一次選很多張）後依序上傳；有上傳成功回傳 true。
  Future<bool> addPhotos() async {
    if (state.busy) return false;
    final images = await ref.read(imagePickerProvider).pickImages();
    if (images == null || images.isEmpty || !ref.mounted) return false;
    state = state.copyWith(busy: true, clearError: true);
    var uploaded = 0;
    try {
      for (final (i, image) in images.indexed) {
        state = state.copyWith(progress: '上傳中 ${i + 1}／${images.length}');
        final rulebook = await _repo.uploadRulebookPhoto(projectId, image);
        uploaded++;
        if (!ref.mounted) return true;
        state = state.copyWith(rulebook: rulebook);
      }
    } on ApiException catch (error) {
      if (ref.mounted) state = state.copyWith(error: error.message);
    }
    if (ref.mounted) {
      state = state.copyWith(busy: false, clearProgress: true);
      ref.invalidate(videoProjectProvider(projectId));
    }
    return uploaded > 0;
  }

  Future<void> delete(int index) async {
    if (state.busy) return;
    state = state.copyWith(busy: true, clearError: true);
    try {
      await _repo.deleteRulebookPhoto(projectId, index);
      final rulebook = await _repo.getRulebook(projectId);
      if (!ref.mounted) return;
      state = state.copyWith(rulebook: rulebook, busy: false);
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(busy: false, error: error.message);
      }
    }
  }

  /// 讀取規則書並產生草稿（開始草稿工作）；成功回傳 true。
  Future<bool> start() async {
    if (!state.canStart) return false;
    state = state.copyWith(busy: true, clearError: true);
    // 工作的進度與錯誤由 videoJobProvider 顯示（專案總覽的進度卡）
    final job = ref.read(videoJobProvider(projectId).notifier);
    unawaited(job.startDraft());
    if (!ref.mounted) return true;
    ref.invalidate(videoProjectProvider(projectId));
    state = state.copyWith(busy: false);
    return true;
  }
}

final videoRulebookProvider = NotifierProvider.autoDispose
    .family<VideoRulebookNotifier, VideoRulebookState, String>(
      VideoRulebookNotifier.new,
    );

/// 一張規則書照片的縮圖；用照片的 id 當 key，刪除後順序變了也不會拿到別張的圖。
typedef RulebookPhotoRef = ({String projectId, int index, String id});

final rulebookPhotoProvider = FutureProvider.autoDispose
    .family<Uint8List, RulebookPhotoRef>(
      (ref, photo) => ref
          .read(videoStudioRepositoryProvider)
          .getRulebookPhoto(photo.projectId, photo.index),
    );
