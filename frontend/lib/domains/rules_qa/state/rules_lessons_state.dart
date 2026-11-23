import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/rules_qa_models.dart';
import '../data/rules_qa_repository.dart';

/// 規則教學的遊戲清單（有規則書或教學影片的遊戲）。
class RulesLessonsNotifier extends AsyncNotifier<List<RulesLessonSummary>> {
  @override
  Future<List<RulesLessonSummary>> build() =>
      ref.read(rulesQaRepositoryProvider).listLessons();

  /// 重新載入（例如載入失敗後按「重試」）。
  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(rulesQaRepositoryProvider).listLessons(),
    );
  }
}

/// 失敗不自動重試（Riverpod 3 預設會重試），交給畫面上的「重試」。
final rulesLessonsProvider =
    AsyncNotifierProvider<RulesLessonsNotifier, List<RulesLessonSummary>>(
      RulesLessonsNotifier.new,
      retry: (_, _) => null,
    );

/// 遊戲清單的篩選。
enum LessonFilter {
  /// 全部遊戲。
  all,

  /// 只看有教學影片的遊戲。
  video,

  /// 只看可以問規則（有規則書）的遊戲。
  rulebook,
}

/// 遊戲清單的搜尋文字與篩選。
@immutable
class LessonsQuery {
  const LessonsQuery({this.search = '', this.filter = LessonFilter.all});

  final String search;
  final LessonFilter filter;

  LessonsQuery copyWith({String? search, LessonFilter? filter}) => LessonsQuery(
    search: search ?? this.search,
    filter: filter ?? this.filter,
  );

  @override
  bool operator ==(Object other) =>
      other is LessonsQuery && other.search == search && other.filter == filter;

  @override
  int get hashCode => Object.hash(search, filter);
}

bool _matchesFilter(RulesLessonSummary item, LessonFilter filter) =>
    switch (filter) {
      LessonFilter.all => true,
      LessonFilter.video => item.hasVideo,
      LessonFilter.rulebook => item.hasRulebook,
    };

/// 依搜尋文字（遊戲名稱部分符合、不分大小寫、忽略前後空白）與篩選過濾，保持原本順序。
List<RulesLessonSummary> filterLessons(
  List<RulesLessonSummary> items,
  LessonsQuery query,
) {
  final search = query.search.trim().toLowerCase();
  return [
    for (final item in items)
      if (_matchesFilter(item, query.filter) &&
          (search.isEmpty || item.gameName.toLowerCase().contains(search)))
        item,
  ];
}

/// 某個篩選有幾款遊戲（篩選膠囊上的數字，不受搜尋影響）。
int lessonCount(List<RulesLessonSummary> items, LessonFilter filter) =>
    items.where((item) => _matchesFilter(item, filter)).length;

/// 目前的搜尋與篩選；離開清單頁後重設。
class LessonsQueryNotifier extends Notifier<LessonsQuery> {
  @override
  LessonsQuery build() => const LessonsQuery();

  void setSearch(String search) => state = state.copyWith(search: search);

  void setFilter(LessonFilter filter) => state = state.copyWith(filter: filter);
}

final lessonsQueryProvider =
    NotifierProvider.autoDispose<LessonsQueryNotifier, LessonsQuery>(
      LessonsQueryNotifier.new,
    );
