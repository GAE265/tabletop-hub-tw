import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/platform/lesson_video_player.dart';
import '../../domains/rules_qa/state/rules_chat_state.dart';
import '../../domains/rules_qa/state/rules_lesson_state.dart';

/// 規則教學參考畫面：教學影片（有的話）＋規則問答。只用預設元件（AGENTS.md 5.4）。
class RulesLessonProtoPage extends ConsumerWidget {
  const RulesLessonProtoPage({required this.gameId, super.key});

  final int gameId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(rulesLessonProvider(gameId));
    final notifier = ref.read(rulesLessonProvider(gameId).notifier);
    return Scaffold(
      appBar: AppBar(title: Text(state.lesson.value?.gameName ?? '規則教學（參考畫面）')),
      body: state.lesson.when(
        skipLoadingOnRefresh: false,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(error is ApiException ? error.message : '發生未知錯誤'),
              ElevatedButton(
                onPressed: () => Navigator.of(context).maybePop(),
                child: const Text('回到遊戲清單'),
              ),
            ],
          ),
        ),
        data: (lesson) => ListView(
          children: [
            if (lesson.video case final video?) ...[
              ref.watch(lessonVideoPlayerProvider).build(context, video),
              if (state.chat == ChatAvailability.waitingForVideo)
                ElevatedButton(
                  onPressed: notifier.startAsking,
                  child: const Text('看完了，開始提問'),
                ),
            ] else
              const ListTile(title: Text('這款遊戲還沒有教學影片，可以直接問規則')),
            switch (state.chat) {
              ChatAvailability.open => _Chat(
                gameId: gameId,
                suggestions: lesson.suggestedQuestions,
              ),
              ChatAvailability.noRulebook => const ListTile(
                title: Text('這款遊戲的規則書還沒入庫，暫時無法提問'),
              ),
              _ => const SizedBox.shrink(),
            },
          ],
        ),
      ),
    );
  }
}

class _Chat extends ConsumerStatefulWidget {
  const _Chat({required this.gameId, required this.suggestions});

  final int gameId;
  final List<String> suggestions;

  @override
  ConsumerState<_Chat> createState() => _ChatState();
}

class _ChatState extends ConsumerState<_Chat> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  RulesChatNotifier get _chat =>
      ref.read(rulesChatProvider(widget.gameId).notifier);

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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(),
        Row(
          children: [
            const Expanded(child: ListTile(title: Text('規則問答'))),
            TextButton(
              onPressed: state.canStartNew ? _chat.startNewConversation : null,
              child: const Text('開始新對話'),
            ),
          ],
        ),
        if (state.notice == RulesChatNotice.expired)
          const ListTile(title: Text('對話已過期，已為你開始新對話')),
        if (state.error case final error?) ListTile(title: Text('錯誤：$error')),
        if (state.messages.isEmpty)
          Wrap(
            children: [
              for (final question in widget.suggestions)
                OutlinedButton(
                  onPressed: sending ? null : () => _chat.send(question),
                  child: Text(question),
                ),
            ],
          ),
        for (final message in state.messages)
          switch (message) {
            QuestionMessage() => ListTile(
              trailing: const Icon(Icons.person),
              title: Text(message.text, textAlign: TextAlign.end),
            ),
            AnswerMessage() => ListTile(
              leading: const Icon(Icons.menu_book_outlined),
              title: Text(message.answer),
              subtitle: message.citations.isEmpty
                  ? null
                  : Text(message.citations.map(citationText).join('、')),
            ),
          },
        if (sending)
          const ListTile(
            leading: CircularProgressIndicator(),
            title: Text('正在查規則…'),
          ),
        TextField(
          key: const Key('rules_qa-input'),
          controller: _input,
          enabled: !sending,
          minLines: 1,
          maxLines: 4,
          onChanged: _chat.editDraft,
          decoration: InputDecoration(
            hintText: '例如：一個回合可以做什麼？',
            helperText: '${state.draftLength} / $rulesQaMaxContentLength 字',
            suffixIcon: IconButton(
              tooltip: '送出',
              icon: const Icon(Icons.send),
              onPressed: state.canSend ? () => _chat.send(state.draft) : null,
            ),
          ),
        ),
      ],
    );
  }
}
