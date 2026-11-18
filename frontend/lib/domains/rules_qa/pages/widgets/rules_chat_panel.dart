import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../state/rules_chat_state.dart';
import 'notice_banner.dart';

/// 規則問答：建議問題、對話紀錄（回答附規則書頁碼）與輸入框。
class RulesChatPanel extends ConsumerStatefulWidget {
  const RulesChatPanel({
    required this.gameId,
    required this.suggestions,
    super.key,
  });

  final int gameId;
  final List<String> suggestions;

  @override
  ConsumerState<RulesChatPanel> createState() => _RulesChatPanelState();
}

class _RulesChatPanelState extends ConsumerState<RulesChatPanel> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  RulesChatNotifier get _chat =>
      ref.read(rulesChatProvider(widget.gameId).notifier);

  /// Enter 送出、Shift+Enter 換行；輸入法還在選字時 Enter 交給輸入法。
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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(child: Text('問規則', style: theme.textTheme.titleLarge)),
            TextButton.icon(
              onPressed: state.canStartNew ? _chat.startNewConversation : null,
              icon: const Icon(Icons.refresh),
              label: const Text('開始新對話'),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.small),
        if (state.notice == RulesChatNotice.expired) ...[
          const NoticeBanner(text: '對話已過期，已為你開始新對話'),
          const SizedBox(height: AppSpacing.small),
        ],
        if (state.error case final error?) ...[
          NoticeBanner(text: error, isError: true),
          const SizedBox(height: AppSpacing.small),
        ],
        if (state.messages.isEmpty && !sending)
          Wrap(
            spacing: AppSpacing.small,
            runSpacing: AppSpacing.small,
            children: [
              for (final question in widget.suggestions)
                ActionChip(
                  label: Text(question),
                  onPressed: () => _chat.send(question),
                ),
            ],
          ),
        for (final message in state.messages)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.medium),
            child: switch (message) {
              QuestionMessage() => _QuestionBubble(message.text),
              AnswerMessage() => _AnswerBubble(message),
            },
          ),
        if (sending)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.medium),
            child: Row(
              children: [
                const SizedBox.square(
                  dimension: AppSpacing.medium,
                  child: CircularProgressIndicator(),
                ),
                const SizedBox(width: AppSpacing.small),
                Text('正在查規則…', style: theme.textTheme.bodyMedium),
              ],
            ),
          ),
        const SizedBox(height: AppSpacing.medium),
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
              helperText:
                  '${state.draftLength} / $rulesQaMaxContentLength 字'
                  '（Enter 送出、Shift+Enter 換行）',
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
      ],
    );
  }
}

class _QuestionBubble extends StatelessWidget {
  const _QuestionBubble(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.primary,
          borderRadius: BorderRadius.circular(AppRadius.card),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.medium,
            vertical: AppSpacing.small,
          ),
          child: Text(
            text,
            style: Theme.of(
              context,
            ).textTheme.bodyLarge!.copyWith(color: scheme.onPrimary),
          ),
        ),
      ),
    );
  }
}

class _AnswerBubble extends StatelessWidget {
  const _AnswerBubble(this.message);

  final AnswerMessage message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
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
        ),
      ),
    );
  }
}
