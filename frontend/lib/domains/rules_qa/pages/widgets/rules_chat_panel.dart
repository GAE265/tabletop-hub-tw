import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/chat_widgets.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../state/rules_chat_state.dart';
import 'notice_banner.dart';

/// 問規則卡片（Stitch 版面）：標題與遊戲名稱、開始新對話、提示、建議問題、對話紀錄。
/// 輸入框是另一個元件 [RulesChatComposer]，由頁面固定在畫面底部。
class RulesChatThread extends ConsumerWidget {
  const RulesChatThread({
    required this.gameId,
    required this.gameName,
    required this.suggestions,
    super.key,
  });

  final int gameId;
  final String gameName;
  final List<String> suggestions;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(rulesChatProvider(gameId));
    final chat = ref.read(rulesChatProvider(gameId).notifier);
    final sending = state.status == RulesChatStatus.sending;
    final text = Theme.of(context).textTheme;

    return ThickCard(
      key: const Key('rules-chat-card'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.forum_outlined, color: AppColors.primaryText),
                const SizedBox(width: AppSpacing.small),
                Text(
                  '問規則',
                  style: text.titleLarge!.copyWith(fontWeight: FontWeight.w700),
                ),
                Expanded(
                  child: Text(
                    '（$gameName）',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: text.titleMedium!.copyWith(
                      color: AppColors.inkMuted,
                    ),
                  ),
                ),
                TextButton.icon(
                  onPressed: state.canStartNew
                      ? chat.startNewConversation
                      : null,
                  icon: const Icon(Icons.refresh),
                  label: const Text('開始新對話'),
                ),
              ],
            ),
            if (state.notice == RulesChatNotice.expired) ...[
              const SizedBox(height: AppSpacing.small),
              const NoticeBanner(text: '對話已過期，已為你開始新對話'),
            ],
            if (state.error case final error?) ...[
              const SizedBox(height: AppSpacing.small),
              NoticeBanner(text: error, isError: true),
            ],
            if (state.messages.isEmpty && !sending) ...[
              const SizedBox(height: AppSpacing.small),
              Text('大家都在問（點了直接發問）', style: text.bodySmall),
              const SizedBox(height: AppSpacing.small),
              Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small + AppSpacing.xSmall,
                children: [
                  for (final question in suggestions)
                    SuggestionChip(
                      label: question,
                      onTap: () => chat.send(question),
                    ),
                ],
              ),
            ],
            for (final message in state.messages)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.medium),
                child: switch (message) {
                  QuestionMessage() => UserBubble(text: message.text),
                  AnswerMessage() => AssistantMessage(
                    name: '規則助理',
                    child: _Answer(message),
                  ),
                },
              ),
            if (sending) ...[
              const SizedBox(height: AppSpacing.medium),
              const ThinkingPill(text: '正在查規則…'),
            ],
          ],
        ),
      ),
    );
  }
}

/// 回答的內容：一段文字，下面是引用的規則書頁碼。
class _Answer extends StatelessWidget {
  const _Answer(this.message);

  final AnswerMessage message;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(message.answer, style: Theme.of(context).textTheme.bodyLarge),
        if (message.citations.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.small),
          Wrap(
            spacing: AppSpacing.small,
            runSpacing: AppSpacing.xSmall,
            children: [
              for (final citation in message.citations)
                PillBadge(
                  label: citationText(citation),
                  tone: PillTone.accent,
                  icon: Icons.menu_book_outlined,
                ),
            ],
          ),
        ],
      ],
    );
  }
}

/// 問規則的輸入區：有厚度的白卡，輸入框與送出鈕，左下操作說明、右下字數。
/// Enter 送出、Shift+Enter 換行；輸入法還在選字時 Enter 交給輸入法。
class RulesChatComposer extends ConsumerStatefulWidget {
  const RulesChatComposer({required this.gameId, super.key});

  final int gameId;

  @override
  ConsumerState<RulesChatComposer> createState() => _RulesChatComposerState();
}

class _RulesChatComposerState extends ConsumerState<RulesChatComposer> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  RulesChatNotifier get _chat =>
      ref.read(rulesChatProvider(widget.gameId).notifier);

  KeyEventResult _onKey(FocusNode node, KeyEvent event) {
    final isEnter =
        event.logicalKey == LogicalKeyboardKey.enter ||
        event.logicalKey == LogicalKeyboardKey.numpadEnter;
    if (event is! KeyDownEvent ||
        !isEnter ||
        HardwareKeyboard.instance.isShiftPressed) {
      return KeyEventResult.ignored;
    }
    final composing = _input.value.composing;
    if (composing.isValid && !composing.isCollapsed) {
      return KeyEventResult.ignored;
    }
    final state = ref.read(rulesChatProvider(widget.gameId));
    if (state.canSend) _chat.send(state.draft);
    return KeyEventResult.handled;
  }

  @override
  Widget build(BuildContext context) {
    // 送出時清空、失敗時放回：輸入框跟著 state 的 draft
    ref.listen(rulesChatProvider(widget.gameId).select((s) => s.draft), (
      _,
      draft,
    ) {
      if (_input.text != draft) _input.text = draft;
    });
    final state = ref.watch(rulesChatProvider(widget.gameId));
    final sending = state.status == RulesChatStatus.sending;
    final theme = Theme.of(context);

    return ThickCard(
      key: const Key('rules-composer'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Focus(
              onKeyEvent: _onKey,
              child: TextField(
                key: const Key('rules-input'),
                controller: _input,
                enabled: !sending,
                minLines: 1,
                maxLines: 4,
                keyboardType: TextInputType.multiline,
                onChanged: _chat.editDraft,
                decoration: InputDecoration(
                  hintText: '例如：一個回合可以做什麼？',
                  suffixIcon: Padding(
                    padding: const EdgeInsets.all(AppSpacing.xSmall),
                    child: IconButton.filled(
                      key: const Key('rules-send'),
                      tooltip: '送出',
                      // 主題的圖示按鈕是深色圖示；主色底的送出鈕要用白色
                      style: ButtonStyle(
                        iconColor: WidgetStateProperty.resolveWith(
                          (states) => states.contains(WidgetState.disabled)
                              ? theme.colorScheme.onSurfaceVariant
                              : theme.colorScheme.onPrimary,
                        ),
                      ),
                      onPressed: state.canSend
                          ? () => _chat.send(state.draft)
                          : null,
                      icon: const Icon(Icons.send),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.small),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Enter 送出、Shift+Enter 換行',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                Text(
                  '${state.draftLength} / $rulesQaMaxContentLength 字',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
