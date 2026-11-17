import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/rules_qa_models.dart';
import '../data/rules_qa_repository.dart';

/// 問答區現在能不能用。
enum ChatAvailability {
  /// 有教學影片，玩家還沒按「看完了，開始提問」。
  waitingForVideo,

  /// 可以提問。
  open,

  /// 只有影片、規則書還沒入庫，暫時無法提問。
  noRulebook,

  /// 教學內容還在載入或載入失敗。
  unavailable,
}

class RulesLessonState {
  const RulesLessonState({required this.lesson, this.askingStarted = false});

  final AsyncValue<RulesLesson> lesson;

  /// 玩家按過「看完了，開始提問」。
  final bool askingStarted;

  ChatAvailability get chat {
    final value = lesson.isLoading ? null : lesson.value;
    if (value == null) return ChatAvailability.unavailable;
    if (value.video != null && !askingStarted) {
      return ChatAvailability.waitingForVideo;
    }
    return value.hasRulebook
        ? ChatAvailability.open
        : ChatAvailability.noRulebook;
  }

  RulesLessonState copyWith({
    AsyncValue<RulesLesson>? lesson,
    bool? askingStarted,
  }) => RulesLessonState(
    lesson: lesson ?? this.lesson,
    askingStarted: askingStarted ?? this.askingStarted,
  );
}

/// 某款遊戲的教學頁：教學內容與「看完影片」的狀態。離開頁面就重置。
class RulesLessonNotifier extends Notifier<RulesLessonState> {
  RulesLessonNotifier(this.gameId);

  final int gameId;
  Future<void> _pending = Future.value();

  /// 目前這次載入完成（測試用來等待）。
  Future<void> get loaded => _pending;

  @override
  RulesLessonState build() {
    _pending = Future.microtask(_fetch);
    return const RulesLessonState(lesson: AsyncLoading());
  }

  Future<void> reload() {
    state = state.copyWith(lesson: const AsyncLoading());
    return _pending = _fetch();
  }

  /// 「看完了，開始提問」。
  void startAsking() => state = state.copyWith(askingStarted: true);

  Future<void> _fetch() async {
    final lesson = await AsyncValue.guard(
      () => ref.read(rulesQaRepositoryProvider).getLesson(gameId),
    );
    if (!ref.mounted) return;
    state = state.copyWith(lesson: lesson);
  }
}

final rulesLessonProvider = NotifierProvider.autoDispose
    .family<RulesLessonNotifier, RulesLessonState, int>(
      RulesLessonNotifier.new,
    );
