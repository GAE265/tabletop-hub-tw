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
  const VideoProjectFormState({this.game, this.submitting = false, this.error});

  final VideoGameOption? game;
  final bool submitting;

  /// 後端回的錯誤說明（例如規則書還沒匯入）。
  final String? error;

  bool get canSubmit => game != null && !submitting;

  VideoProjectFormState copyWith({
    VideoGameOption? game,
    bool? submitting,
    String? error,
    bool clearError = false,
  }) => VideoProjectFormState(
    game: game ?? this.game,
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

  /// 送出；成功回傳新專案並重新載入列表，失敗回傳 null（說明在 `error`）。
  Future<VideoProject?> submit() async {
    if (!state.canSubmit) return null;
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final project = await ref
          .read(videoStudioRepositoryProvider)
          .createProject(VideoProjectCreate(gameId: state.game!.id));
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
