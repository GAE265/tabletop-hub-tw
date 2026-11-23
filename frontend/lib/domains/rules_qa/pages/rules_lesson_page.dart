import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/chat_widgets.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/platform/lesson_video_player.dart';
import '../../../core/widgets/size_reporter.dart';
import '../data/rules_qa_models.dart';
import '../state/rules_lesson_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/rules_chat_panel.dart';

/// 某款遊戲的教學頁：有影片先看影片，看完再問；沒有影片直接問。
/// 手機版影片在上、問答在下；平板與桌機有影片時左右並排。
///
/// Stitch 版面（docs/ui/stitch/）：木紋背景，頁首白底條（返回、遊戲名稱），影片卡與問規則卡有厚度；
/// 可以提問時，輸入區固定在畫面底部、浮在內容上，內容從後面滑過去。
/// 手機的浮動導覽列蓋住的高度（MediaQuery 底部 padding）留在輸入區下方。
class RulesLessonPage extends ConsumerWidget {
  const RulesLessonPage({required this.gameId, super.key});

  final int gameId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(rulesLessonProvider(gameId));
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium,
            0,
          ),
          child: _Header(title: state.lesson.value?.gameName ?? '規則教學'),
        ),
        Expanded(
          child: state.lesson.when(
            skipLoadingOnRefresh: false,
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _LoadError(error: error),
            data: (lesson) => _LessonBody(lesson: lesson, state: state),
          ),
        ),
      ],
    );
    return Scaffold(
      key: const Key('rules-lesson-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? body
            : WoodBackground(child: body),
      ),
    );
  }
}

/// 回到遊戲清單：能返回就返回，否則前往 `/rules`。
void _back(BuildContext context) {
  if (Navigator.of(context).canPop()) {
    Navigator.of(context).pop();
  } else {
    GoRouter.maybeOf(context)?.go('/rules');
  }
}

/// 頁首白底條：返回鍵與遊戲名稱。
class _Header extends StatelessWidget {
  const _Header({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return GlassBar(
      key: const Key('rules-lesson-header'),
      child: Row(
        children: [
          IconButton(
            key: const Key('rules-lesson-back'),
            tooltip: '回到遊戲清單',
            onPressed: () => _back(context),
            icon: const Icon(Icons.arrow_back),
          ),
          const SizedBox(width: AppSpacing.xSmall),
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.error});

  final Object error;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: ThickCard(
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
    final chatOpen = state.chat == ChatAvailability.open;
    final videoSection = video == null
        ? null
        : _VideoSection(
            video: video,
            waiting: state.chat == ChatAvailability.waitingForVideo,
            onStart: ref
                .read(rulesLessonProvider(lesson.gameId).notifier)
                .startAsking,
          );
    final chat = _ChatSection(lesson: lesson, availability: state.chat);

    // 平板與桌機有影片：左邊影片、右邊問答（輸入區固定在右欄底部）
    if (videoSection != null && context.screenSize != ScreenSize.mobile) {
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
                  padding: const EdgeInsets.all(AppSpacing.medium),
                  child: videoSection,
                ),
              ),
              Expanded(
                flex: 2,
                child: _FloatingComposerColumn(
                  gameId: lesson.gameId,
                  showComposer: chatOpen,
                  children: [chat],
                ),
              ),
            ],
          ),
        ),
      );
    }

    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: _FloatingComposerColumn(
          gameId: lesson.gameId,
          showComposer: chatOpen,
          children: [
            if (videoSection != null) ...[
              videoSection,
              const SizedBox(height: AppSpacing.medium),
            ],
            chat,
          ],
        ),
      ),
    );
  }
}

/// 可以捲動的內容，加上浮在最下面的輸入區（[showComposer] 時）。
/// 內容從輸入區後面滑過去；捲到底時，最後的內容停在輸入區上方。
class _FloatingComposerColumn extends StatefulWidget {
  const _FloatingComposerColumn({
    required this.gameId,
    required this.showComposer,
    required this.children,
  });

  final int gameId;
  final bool showComposer;
  final List<Widget> children;

  @override
  State<_FloatingComposerColumn> createState() =>
      _FloatingComposerColumnState();
}

class _FloatingComposerColumnState extends State<_FloatingComposerColumn> {
  double _composerHeight = 0;

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final bottomSpace = widget.showComposer
        ? _composerHeight
        : AppSpacing.medium + bottomInset;
    return Stack(
      children: [
        Positioned.fill(
          child: TopEdgeFade(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(
                AppSpacing.medium,
                AppSpacing.medium,
                AppSpacing.medium,
                bottomSpace,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: widget.children,
              ),
            ),
          ),
        ),
        if (widget.showComposer)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SizeReporter(
              onHeight: (height) {
                if (mounted && height != _composerHeight) {
                  setState(() => _composerHeight = height);
                }
              },
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.medium,
                  AppSpacing.small,
                  AppSpacing.medium,
                  AppSpacing.medium + bottomInset,
                ),
                child: RulesChatComposer(gameId: widget.gameId),
              ),
            ),
          ),
      ],
    );
  }
}

/// 影片卡：標題「教學影片」、播放器、影片標題，還沒開始提問時有「看完了，開始提問」。
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
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('rules-video-card'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.smart_display_outlined,
                  color: AppColors.primaryText,
                ),
                const SizedBox(width: AppSpacing.small),
                Text(
                  '教學影片',
                  style: text.titleLarge!.copyWith(fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
            ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.card),
              child: ref.watch(lessonVideoPlayerProvider).build(context, video),
            ),
            const SizedBox(height: AppSpacing.small),
            Text(video.title, style: text.titleMedium),
            if (waiting) ...[
              const SizedBox(height: AppSpacing.medium),
              ThickButton(
                style: ThickStyle.primary,
                expand: true,
                onPressed: onStart,
                icon: Icons.question_answer_outlined,
                label: '看完了，開始提問',
              ),
            ],
          ],
        ),
      ),
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
          ChatAvailability.open => RulesChatThread(
            gameId: lesson.gameId,
            gameName: lesson.gameName,
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
