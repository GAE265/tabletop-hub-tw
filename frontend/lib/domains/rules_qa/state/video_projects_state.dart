import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 章節標題去掉前後空白後 1–50 字（與後端相同）。
const videoChapterTitleMaxChars = 50;

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

/// 建立專案時可選的遊戲。
final videoGameOptionsProvider = FutureProvider<List<VideoGameOption>>(
  (ref) => ref.read(videoStudioRepositoryProvider).listGames(),
  retry: (_, _) => null,
);

class VideoProjectFormState {
  const VideoProjectFormState({
    this.game,
    this.chapterNumberInput = '',
    this.chapterTitleInput = '',
    this.submitting = false,
    this.error,
  });

  final VideoGameOption? game;
  final String chapterNumberInput;
  final String chapterTitleInput;
  final bool submitting;

  /// 後端回的錯誤說明（例如遊戲不存在）。
  final String? error;

  int? get chapterNumber {
    final value = int.tryParse(chapterNumberInput.trim());
    return value != null && value >= 1 ? value : null;
  }

  String get chapterTitle => chapterTitleInput.trim();

  bool get titleValid =>
      chapterTitle.isNotEmpty &&
      chapterTitle.length <= videoChapterTitleMaxChars;

  bool get canSubmit =>
      game != null && chapterNumber != null && titleValid && !submitting;

  VideoProjectFormState copyWith({
    VideoGameOption? game,
    String? chapterNumberInput,
    String? chapterTitleInput,
    bool? submitting,
    String? error,
    bool clearError = false,
  }) => VideoProjectFormState(
    game: game ?? this.game,
    chapterNumberInput: chapterNumberInput ?? this.chapterNumberInput,
    chapterTitleInput: chapterTitleInput ?? this.chapterTitleInput,
    submitting: submitting ?? this.submitting,
    error: clearError ? null : error ?? this.error,
  );
}

/// 建立專案的表單。畫面打開時呼叫 [reset]。
class VideoProjectFormNotifier extends Notifier<VideoProjectFormState> {
  @override
  VideoProjectFormState build() => const VideoProjectFormState();

  void reset() => state = const VideoProjectFormState();

  void selectGame(VideoGameOption game) =>
      state = state.copyWith(game: game, clearError: true);

  void setChapterNumber(String input) =>
      state = state.copyWith(chapterNumberInput: input, clearError: true);

  void setChapterTitle(String input) =>
      state = state.copyWith(chapterTitleInput: input, clearError: true);

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
              chapterNumber: state.chapterNumber!,
              chapterTitle: state.chapterTitle,
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
