import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 確認差異畫面的一處差異：改過的有原文與編輯後；刪掉的只有原文（[edited] 為 null）。
class PageDifference {
  const PageDifference({
    required this.page,
    required this.original,
    this.edited,
  });

  final int page;
  final String original;
  final String? edited;

  bool get removed => edited == null;
}

class VideoPagesState {
  const VideoPagesState({
    this.pages,
    this.texts = const {},
    this.loading = false,
    this.saving = false,
    this.dirty = false,
    this.error,
  });

  /// 後端最近一次回傳的頁面（含差異）。
  final VideoPages? pages;

  /// 畫面上目前的文字（頁碼 → 文字）；可能還沒儲存。
  final Map<int, String> texts;
  final bool loading;
  final bool saving;

  /// 有改過文字還沒儲存。
  final bool dirty;
  final String? error;

  /// 已儲存的差異：每頁先列改過的行，再列刪掉的段落；每一處都附原文。
  List<PageDifference> get differences => [
    for (final page in pages?.pages ?? const <VideoPageText>[]) ...[
      for (final change in page.changed)
        PageDifference(
          page: page.page,
          original: change.original,
          edited: change.edited,
        ),
      for (final block in page.removed)
        PageDifference(page: page.page, original: block.lines.join('\n')),
    ],
  ];

  VideoPagesState copyWith({
    VideoPages? pages,
    Map<int, String>? texts,
    bool? loading,
    bool? saving,
    bool? dirty,
    String? error,
    bool clearError = false,
  }) => VideoPagesState(
    pages: pages ?? this.pages,
    texts: texts ?? this.texts,
    loading: loading ?? this.loading,
    saving: saving ?? this.saving,
    dirty: dirty ?? this.dirty,
    error: clearError ? null : error ?? this.error,
  );
}

/// 選頁與編輯文字（add-rules-video-mobile design.md D11、D12）。
class VideoPagesNotifier extends Notifier<VideoPagesState> {
  VideoPagesNotifier(this.projectId);

  final String projectId;

  @override
  VideoPagesState build() => const VideoPagesState();

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final pages = await ref
          .read(videoStudioRepositoryProvider)
          .getPages(projectId);
      state = _loaded(pages).copyWith(loading: false);
    } on ApiException catch (error) {
      state = state.copyWith(loading: false, error: error.message);
    }
  }

  void editText(int page, String text) => state = state.copyWith(
    texts: {...state.texts, page: text},
    dirty: true,
    clearError: true,
  );

  /// 換選頁並立刻儲存：還在的頁保留目前的文字，新選的頁用原文。
  Future<bool> selectPages({
    required List<int> chapter,
    List<int> reference = const [],
  }) => _save(chapter, reference);

  /// 儲存目前的文字（選頁不變）。
  Future<bool> save() => _save(
    state.pages?.chapterPages ?? const [],
    state.pages?.referencePages ?? const [],
  );

  Future<bool> _save(List<int> chapter, List<int> reference) async {
    final selected = {...chapter, ...reference};
    final texts = {
      for (final entry in state.texts.entries)
        if (selected.contains(entry.key)) '${entry.key}': entry.value,
    };
    state = state.copyWith(saving: true, clearError: true);
    try {
      final pages = await ref
          .read(videoStudioRepositoryProvider)
          .savePages(
            projectId,
            VideoPagesUpdate(
              chapterPages: chapter,
              referencePages: reference,
              texts: texts,
            ),
          );
      state = _loaded(pages).copyWith(saving: false);
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(saving: false, error: _message(error));
      return false;
    }
  }

  VideoPagesState _loaded(VideoPages pages) => VideoPagesState(
    pages: pages,
    texts: {for (final page in pages.pages) page.page: page.text},
  );

  /// 缺頁時請管理員先匯入（店員這一版不能自己匯入，design.md D12）。
  static String _message(ApiException error) {
    if (error.code == 'RULES_VIDEO_PAGES_MISSING') {
      final missing = (error.details['missing'] as List<dynamic>? ?? const [])
          .map((page) => '$page')
          .join('、');
      return '請管理員先匯入第 $missing 頁';
    }
    return error.message;
  }
}

/// 留在記憶體裡：離開頁面再回來，未儲存的文字還在。
final videoPagesProvider =
    NotifierProvider.family<VideoPagesNotifier, VideoPagesState, String>(
      VideoPagesNotifier.new,
    );
