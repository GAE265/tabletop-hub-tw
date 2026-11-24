import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 影片專案列表（自己店的；管理員看全部）。
class VideoProjectsNotifier extends AsyncNotifier<List<VideoProject>> {
  @override
  Future<List<VideoProject>> build() =>
      ref.read(videoStudioRepositoryProvider).listProjects();

  /// 重新載入（例如載入失敗後按「重試」、建立專案後回到列表）。
  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(videoStudioRepositoryProvider).listProjects(),
    );
  }
}

/// 失敗不自動重試，交給畫面上的「重試」。
final videoProjectsProvider =
    AsyncNotifierProvider<VideoProjectsNotifier, List<VideoProject>>(
      VideoProjectsNotifier.new,
      retry: (_, _) => null,
    );

class VideoProjectDeleteState {
  const VideoProjectDeleteState({this.deleting = false, this.error});

  final bool deleting;

  /// 後端回的說明（例如正在產生草稿或影片時的 409）。
  final String? error;
}

/// 刪除專案（2026-11-24 永傑決定，最小版）：成功後重新載入專案列表；畫面負責先確認、再回到列表。
class VideoProjectDeleteNotifier extends Notifier<VideoProjectDeleteState> {
  VideoProjectDeleteNotifier(this.projectId);

  final String projectId;

  @override
  VideoProjectDeleteState build() => const VideoProjectDeleteState();

  /// 刪除；成功回傳 true。刪除中再呼叫不重複送出，回傳 false。
  Future<bool> delete() async {
    if (state.deleting) return false;
    state = const VideoProjectDeleteState(deleting: true);
    try {
      await ref.read(videoStudioRepositoryProvider).deleteProject(projectId);
    } on ApiException catch (error) {
      if (ref.mounted) state = VideoProjectDeleteState(error: error.message);
      return false;
    }
    ref.invalidate(videoProjectsProvider);
    if (ref.mounted) state = const VideoProjectDeleteState();
    return true;
  }
}

final videoProjectDeleteProvider = NotifierProvider.autoDispose
    .family<VideoProjectDeleteNotifier, VideoProjectDeleteState, String>(
      VideoProjectDeleteNotifier.new,
    );

/// 單一專案（專案總覽）。草稿工作完成時會重新讀取（步驟會變）。
final videoProjectProvider = FutureProvider.family<VideoProject, String>(
  (ref, projectId) =>
      ref.read(videoStudioRepositoryProvider).getProject(projectId),
  retry: (_, _) => null,
);

/// 建立專案時可選的遊戲。
final videoGameOptionsProvider = FutureProvider<List<VideoGameOption>>(
  (ref) => ref.read(videoStudioRepositoryProvider).listGames(),
  retry: (_, _) => null,
);

class VideoProjectFormState {
  const VideoProjectFormState({
    this.game,
    this.rulebook = 'imported',
    this.submitting = false,
    this.error,
  });

  final VideoGameOption? game;

  /// 規則書來源：imported＝已匯入的規則書；photos＝店員拍規則書。
  final String rulebook;
  final bool submitting;

  /// 後端回的錯誤說明（例如規則書還沒匯入）。
  final String? error;

  bool get canSubmit => game != null && !submitting;

  VideoProjectFormState copyWith({
    VideoGameOption? game,
    String? rulebook,
    bool? submitting,
    String? error,
    bool clearError = false,
  }) => VideoProjectFormState(
    game: game ?? this.game,
    rulebook: rulebook ?? this.rulebook,
    submitting: submitting ?? this.submitting,
    error: clearError ? null : error ?? this.error,
  );
}

/// 建立專案的表單：只選遊戲（整個遊戲一支影片，D17）。畫面打開時呼叫 [reset]。
/// 建立後後端自動開始產生草稿。
class VideoProjectFormNotifier extends Notifier<VideoProjectFormState> {
  @override
  VideoProjectFormState build() => const VideoProjectFormState();

  void reset() => state = const VideoProjectFormState();

  void selectGame(VideoGameOption game) =>
      state = state.copyWith(game: game, clearError: true);

  void selectRulebook(String rulebook) =>
      state = state.copyWith(rulebook: rulebook, clearError: true);

  /// 送出；成功回傳新專案並重新載入列表，失敗回傳 null（說明在 `error`）。
  Future<VideoProject?> submit() async {
    if (!state.canSubmit) return null;
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final project = await ref
          .read(videoStudioRepositoryProvider)
          .createProject(
            VideoProjectCreate(
              gameId: state.game!.id,
              rulebook: state.rulebook == 'photos' ? 'photos' : null,
            ),
          );
      state = state.copyWith(submitting: false);
      ref.invalidate(videoProjectsProvider);
      return project;
    } on ApiException catch (error) {
      state = state.copyWith(submitting: false, error: error.message);
      return null;
    }
  }
}

final videoProjectFormProvider =
    NotifierProvider<VideoProjectFormNotifier, VideoProjectFormState>(
      VideoProjectFormNotifier.new,
    );
