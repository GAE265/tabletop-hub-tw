import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/platform/lesson_video_player.dart';
import '../data/rules_qa_models.dart';
import '../state/rules_lesson_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/rules_chat_panel.dart';

/// 某款遊戲的教學頁：有影片先看影片，看完再問；沒有影片直接問。
/// 手機版影片在上、問答在下；平板與桌機有影片時左右並排。
class RulesLessonPage extends ConsumerWidget {
  const RulesLessonPage({required this.gameId, super.key});

  final int gameId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(rulesLessonProvider(gameId));
    return Scaffold(
      key: const Key('rules-lesson-page'),
      appBar: AppBar(title: Text(state.lesson.value?.gameName ?? '規則教學')),
      body: state.lesson.when(
        skipLoadingOnRefresh: false,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _LoadError(error: error),
        data: (lesson) => _LessonBody(lesson: lesson, state: state),
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.error});

  final Object error;

  void _back(BuildContext context) {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    } else {
      GoRouter.maybeOf(context)?.go('/rules');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.large),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              error is ApiException
                  ? (error as ApiException).message
                  : '發生未知錯誤',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.medium),
            OutlinedButton(
              onPressed: () => _back(context),
              child: const Text('回到遊戲清單'),
            ),
          ],
        ),
      ),
    );
  }
}

class _LessonBody extends ConsumerWidget {
  const _LessonBody({required this.lesson, required this.state});

  final RulesLesson lesson;
  final RulesLessonState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final video = lesson.video;
    final chat = _ChatSection(lesson: lesson, availability: state.chat);
    const padding = EdgeInsets.all(AppSpacing.medium);

    if (video == null) {
      final maxWidth =
          AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
      return Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: SingleChildScrollView(padding: padding, child: chat),
        ),
      );
    }

    final videoSection = _VideoSection(
      video: video,
      waiting: state.chat == ChatAvailability.waitingForVideo,
      onStart: ref
          .read(rulesLessonProvider(lesson.gameId).notifier)
          .startAsking,
    );

    if (context.screenSize == ScreenSize.mobile) {
      return SingleChildScrollView(
        padding: padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            videoSection,
            const SizedBox(height: AppSpacing.large),
            chat,
          ],
        ),
      );
    }
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.splitContentMaxWidth,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 3,
              child: SingleChildScrollView(
                padding: padding,
                child: videoSection,
              ),
            ),
            Expanded(
              flex: 2,
              child: SingleChildScrollView(padding: padding, child: chat),
            ),
          ],
        ),
      ),
    );
  }
}

class _VideoSection extends ConsumerWidget {
  const _VideoSection({
    required this.video,
    required this.waiting,
    required this.onStart,
  });

  final LessonVideo video;
  final bool waiting;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.card),
          child: ref.watch(lessonVideoPlayerProvider).build(context, video),
        ),
        const SizedBox(height: AppSpacing.small),
        Text(video.title, style: Theme.of(context).textTheme.titleMedium),
        if (waiting) ...[
          const SizedBox(height: AppSpacing.medium),
          FilledButton.icon(
            onPressed: onStart,
            icon: const Icon(Icons.question_answer_outlined),
            label: const Text('看完了，開始提問'),
          ),
        ],
      ],
    );
  }
}

/// 問答區：依目前狀態顯示問答、提示，或什麼都不顯示（還在看影片）。
class _ChatSection extends StatelessWidget {
  const _ChatSection({required this.lesson, required this.availability});

  final RulesLesson lesson;
  final ChatAvailability availability;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const Key('rules-chat'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (lesson.video == null && lesson.hasRulebook) ...[
          const NoticeBanner(text: '這款遊戲還沒有教學影片，可以直接問規則'),
          const SizedBox(height: AppSpacing.medium),
        ],
        switch (availability) {
          ChatAvailability.open => RulesChatPanel(
            gameId: lesson.gameId,
            suggestions: lesson.suggestedQuestions,
          ),
          ChatAvailability.noRulebook => const NoticeBanner(
            text: '這款遊戲的規則書還沒入庫，暫時無法提問',
          ),
          _ => const SizedBox.shrink(),
        },
      ],
    );
  }
}
