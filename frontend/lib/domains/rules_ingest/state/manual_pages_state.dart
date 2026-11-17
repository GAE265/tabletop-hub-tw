import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/platform/image_picker.dart';
import '../data/game_option.dart';
import '../data/game_search_repository.dart';
import '../data/manual_page.dart';
import '../data/manual_pages_repository.dart';

int? positiveInteger(String text) {
  if (!RegExp(r'^[0-9]+$').hasMatch(text.trim())) return null;
  final value = int.tryParse(text.trim());
  return value != null && value > 0 ? value : null;
}

String operationError(Object error) {
  if (error is ApiException) {
    return error.statusCode == 403
        ? '${error.message}；請切換成 shop_staff 或 admin'
        : error.message;
  }
  return '操作失敗，請稍後重試';
}

class ManualPagesState {
  const ManualPagesState({
    this.data,
    this.gamesId,
    this.loading = false,
    this.error,
  });
  final ManualPageList? data;
  final int? gamesId;
  final bool loading;
  final String? error;
}

class ManualPagesNotifier extends Notifier<ManualPagesState> {
  @override
  ManualPagesState build() => const ManualPagesState();

  Future<void> load(String input) async {
    if (state.loading) return;
    final gamesId = positiveInteger(input);
    if (gamesId == null) {
      state = ManualPagesState(
        data: state.data,
        gamesId: state.gamesId,
        error: '桌遊編號必須是正整數',
      );
      return;
    }
    final previous = state;
    state = ManualPagesState(
      data: previous.data,
      gamesId: previous.gamesId,
      loading: true,
    );
    try {
      final data = await ref.read(manualPagesRepositoryProvider).list(gamesId);
      state = ManualPagesState(data: data, gamesId: gamesId);
    } catch (error) {
      state = ManualPagesState(
        data: previous.data,
        gamesId: previous.gamesId,
        error: operationError(error),
      );
    }
  }
}

final manualPagesProvider =
    NotifierProvider<ManualPagesNotifier, ManualPagesState>(
      ManualPagesNotifier.new,
    );

class PageImportResult {
  const PageImportResult({
    required this.page,
    required this.filename,
    this.content,
    this.error,
  });
  final int page;
  final String filename;
  final String? content;
  final String? error;
  bool get success => error == null;
}

class ManualImportState {
  const ManualImportState({
    this.gamesQuery = '',
    this.gamesId,
    this.selectedGame,
    this.allGames = const [],
    this.startPageInput = '1',
    this.images = const [],
    this.results = const [],
    this.importing = false,
    this.picking = false,
    this.current = 0,
    this.error,
    this.gamesLoading = false,
  });
  final String gamesQuery;
  final int? gamesId;
  final GameOption? selectedGame;
  final List<GameOption> allGames;
  final String startPageInput;
  final List<PickedImage> images;
  final List<PageImportResult> results;
  final bool importing;
  final bool picking;
  final int current;
  final String? error;
  final bool gamesLoading;

  /// 依目前輸入字串從 allGames 裡過濾，不分大小寫比對中英文名稱。
  /// 輸入空白時顯示全部。
  List<GameOption> get filteredOptions {
    final q = gamesQuery.trim().toLowerCase();
    if (q.isEmpty) return allGames;
    return allGames.where((g) =>
        g.name.toLowerCase().contains(q) ||
        g.englishName.toLowerCase().contains(q)).toList();
  }

  /// 輸入的名稱已對應到一款桌遊（id 有值）才算有效。
  bool get validInput =>
      selectedGame != null && positiveInteger(startPageInput) != null;
  bool get canImport =>
      validInput && images.isNotEmpty && !importing && !picking;

  ManualImportState copyWith({
    String? gamesQuery,
    int? gamesId,
    GameOption? selectedGame,
    bool clearSelectedGame = false,
    List<GameOption>? allGames,
    String? startPageInput,
    List<PickedImage>? images,
    List<PageImportResult>? results,
    bool? importing,
    bool? picking,
    int? current,
    String? error,
    bool? gamesLoading,
  }) => ManualImportState(
    gamesQuery: gamesQuery ?? this.gamesQuery,
    gamesId: clearSelectedGame ? null : (gamesId ?? this.gamesId),
    selectedGame: clearSelectedGame ? null : (selectedGame ?? this.selectedGame),
    allGames: allGames ?? this.allGames,
    startPageInput: startPageInput ?? this.startPageInput,
    images: images ?? this.images,
    results: results ?? this.results,
    importing: importing ?? this.importing,
    picking: picking ?? this.picking,
    current: current ?? this.current,
    error: error,
    gamesLoading: gamesLoading ?? this.gamesLoading,
  );
}

class ManualImportNotifier extends Notifier<ManualImportState> {
  @override
  ManualImportState build() {
    Future.microtask(_loadAllGames);
    return const ManualImportState();
  }

  Future<void> _loadAllGames() async {
    state = state.copyWith(gamesLoading: true);
    try {
      final allGames = await ref.read(gameSearchRepositoryProvider).listAll();
      state = state.copyWith(allGames: allGames, gamesLoading: false);
    } catch (error) {
      state = state.copyWith(
        allGames: const [],
        gamesLoading: false,
        error: operationError(error),
      );
    }
  }

  /// 使用者打字時更新搜尋字串，filteredOptions 會自動從 allGames 過濾。
  void setGamesQuery(String value) {
    if (state.importing || state.picking) return;
    state = state.copyWith(
      gamesQuery: value,
      clearSelectedGame: true,
      error: null,
    );
  }

  /// 從下拉選單選定一款桌遊，之後匯入都寫到這個 games_id。
  void selectGame(GameOption game) {
    if (state.importing || state.picking) return;
    state = state.copyWith(
      gamesQuery: game.name,
      gamesId: game.id,
      selectedGame: game,
      error: null,
    );
  }

  void setStartPageInput(String value) {
    if (state.importing || state.picking) return;
    state = state.copyWith(
      startPageInput: value,
      error: positiveInteger(value) == null ? '起始頁碼必須大於或等於 1' : null,
    );
  }

  void reorderImages(int oldIndex, int newIndex) {
    if (state.importing || state.picking) return;
    final images = [...state.images];
    final item = images.removeAt(oldIndex);
    images.insert(newIndex.clamp(0, images.length - 1), item);
    state = state.copyWith(images: List.unmodifiable(images));
  }

  void removeImage(int index) {
    if (state.importing || state.picking) return;
    final images = [...state.images]..removeAt(index);
    state = state.copyWith(images: List.unmodifiable(images));
  }

  Future<void> pickImages() async {
    if (state.importing || state.picking) return;
    state = state.copyWith(picking: true);
    try {
      final images = await ref.read(imagePickerProvider).pickImages();
      if (images != null) {
        final sorted = [...images]..sort((a, b) => a.name.compareTo(b.name));
        state = state.copyWith(
          images: List.unmodifiable(sorted),
          results: const [],
          current: 0,
        );
      }
    } catch (error) {
      state = state.copyWith(error: operationError(error));
    } finally {
      state = state.copyWith(picking: false, error: state.error);
    }
  }

  Future<void> importPages() async {
    if (state.importing || state.picking) return;
    if (!state.canImport) {
      state = state.copyWith(error: '請選擇一款桌遊、起始頁碼並選擇圖片');
      return;
    }
    final gamesId = state.gamesId!;
    final startPage = positiveInteger(state.startPageInput)!;
    final images = state.images;
    // 整批沿用同一個 repository，避免匯入途中更換依賴。
    final repository = ref.read(manualPagesRepositoryProvider);
    state = state.copyWith(importing: true, results: const [], current: 0);
    try {
      for (var index = 0; index < images.length; index++) {
        final image = images[index];
        final page = startPage + index;
        state = state.copyWith(current: index + 1);
        PageImportResult result;
        try {
          final output = await repository.importPage(gamesId, page, image);
          result = PageImportResult(
            page: page,
            filename: image.name,
            content: output.content,
          );
        } catch (error) {
          result = PageImportResult(
            page: page,
            filename: image.name,
            error: operationError(error),
          );
        }
        state = state.copyWith(
          results: List.unmodifiable([...state.results, result]),
        );
      }
      await ref.read(manualPagesProvider.notifier).load(gamesId.toString());
    } finally {
      state = state.copyWith(importing: false);
    }
  }
}

final manualImportProvider =
    NotifierProvider<ManualImportNotifier, ManualImportState>(
      ManualImportNotifier.new,
    );
