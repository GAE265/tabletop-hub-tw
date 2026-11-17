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
