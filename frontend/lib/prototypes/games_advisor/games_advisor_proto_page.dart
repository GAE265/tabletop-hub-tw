import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/games_advisor/data/advisor_message.dart';
import '../../domains/games_advisor/state/advisor_state.dart';
import '../../domains/games_advisor/state/game_card_text.dart';

/// 推薦 Agent 參考畫面：只用預設元件，不調顏色、字型、間距，不做 RWD（AGENTS.md 5.4）。
/// 所有操作都交給 `advisorProvider`，正式頁面用同一份 state。
class GamesAdvisorProtoPage extends ConsumerStatefulWidget {
  const GamesAdvisorProtoPage({super.key});

  @override
  ConsumerState<GamesAdvisorProtoPage> createState() =>
      _GamesAdvisorProtoPageState();
}

/// 空畫面的範例按鈕，點了直接送出（spec §14.3）。
const _examples = ['我們 4 個人，想輕鬆聊天', '2 個人約會玩', '6 個人，30 分鐘內玩完'];

class _GamesAdvisorProtoPageState extends ConsumerState<GamesAdvisorProtoPage> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  AdvisorNotifier get _advisor => ref.read(advisorProvider.notifier);

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
    final state = ref.read(advisorProvider);
    if (state.canSend) _advisor.sendMessage(state.draft);
    return KeyEventResult.handled;
  }

  @override
  Widget build(BuildContext context) {
    // 送出時清空、失敗時放回：輸入框跟著 state 的 draft
    ref.listen(advisorProvider.select((s) => s.draft), (_, draft) {
      if (_input.text != draft) _input.text = draft;
    });
    final state = ref.watch(advisorProvider);
    final sending = state.status == AdvisorStatus.sending;

    return Scaffold(
      key: const Key('games_advisor-proto-page'),
      appBar: AppBar(
        title: const Text('推薦 Agent（參考畫面）'),
        actions: [
          // 目前主題的 TextButton 和 AppBar 同色會看不見，所以用 tonal
          FilledButton.tonal(
            onPressed: state.canStartNew ? _advisor.startNewConversation : null,
            child: const Text('開始新對話'),
          ),
        ],
      ),
      body: Column(
        children: [
          if (state.notice != null) _NoticeBar(state.notice!),
          Expanded(
            child: state.messages.isEmpty && !sending
                ? _EmptyView(onExample: _advisor.sendMessage)
                : ListView(
                    children: [
                      for (final message in state.messages)
                        switch (message) {
                          PlayerMessage() => _PlayerBubble(message),
                          AdvisorReplyMessage() => _AdvisorReply(message),
                        },
                      if (sending)
                        const ListTile(
                          leading: CircularProgressIndicator(),
                          title: Text('正在找桌遊…'),
                        ),
                    ],
                  ),
          ),
          const Divider(),
          Focus(
            onKeyEvent: _onKey,
            child: TextField(
              controller: _input,
              enabled: !sending,
              minLines: 1,
              maxLines: 4,
              keyboardType: TextInputType.multiline,
              onChanged: _advisor.editDraft,
              decoration: InputDecoration(
                hintText: '例如：我們 4 個人，想玩 1 小時內、輕鬆聊天的',
                helperText:
                    '${state.draftLength} / $advisorMaxContentLength 字'
                    '（Enter 送出、Shift+Enter 換行）',
                suffixIcon: IconButton(
                  tooltip: '送出',
                  icon: const Icon(Icons.send),
                  onPressed: state.canSend
                      ? () => _advisor.sendMessage(state.draft)
                      : null,
                ),
              ),
            ),
          ),
          // 🚧 rules_qa 還沒有頁面，先留位置；有頁面後改成連過去
          const TextButton(onPressed: null, child: Text('想問規則或玩法？到規則問答')),
        ],
      ),
    );
  }
}

class _NoticeBar extends StatelessWidget {
  const _NoticeBar(this.notice);

  final AdvisorNotice notice;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.info_outline),
      title: Text(switch (notice) {
        AdvisorNotice.expired => '對話已失效，請開始新對話',
        AdvisorNotice.unavailable => '推薦 Agent 暫時無法回應，請再送一次',
      }),
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView({required this.onExample});

  final void Function(String content) onExample;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('告訴我幾個人、想玩多久、喜歡什麼感覺，我幫你挑桌遊。'),
          for (final example in _examples)
            OutlinedButton(
              onPressed: () => onExample(example),
              child: Text(example),
            ),
        ],
      ),
    );
  }
}

class _PlayerBubble extends StatelessWidget {
  const _PlayerBubble(this.message);

  final PlayerMessage message;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      trailing: const Icon(Icons.person),
      title: Text(message.text, textAlign: TextAlign.end),
    );
  }
}

class _AdvisorReply extends StatelessWidget {
  const _AdvisorReply(this.message);

  final AdvisorReplyMessage message;

  @override
  Widget build(BuildContext context) {
    final relaxed = message.relaxedConstraint;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ListTile(
          leading: const Icon(Icons.smart_toy_outlined),
          title: Text(message.reply),
        ),
        if (relaxed != null && message.recommendations.isNotEmpty)
          ListTile(
            leading: const Icon(Icons.tune),
            title: Text(relaxedConstraintText(relaxed)),
          ),
        for (final recommendation in message.recommendations)
          _GameCard(recommendation),
      ],
    );
  }
}

class _GameCard extends StatelessWidget {
  const _GameCard(this.recommendation);

  final AdvisorRecommendation recommendation;

  @override
  Widget build(BuildContext context) {
    final excerpts = recommendation.excerpts;
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            title: Text(recommendation.game.name),
            subtitle: Text(gameMetaText(recommendation.game)),
          ),
          ListTile(title: Text(recommendation.reason)),
          if (excerpts.isNotEmpty)
            ExpansionTile(
              title: Text('心得片段（${excerpts.length}）'),
              children: [
                for (final excerpt in excerpts)
                  ListTile(
                    title: Text(excerpt.text),
                    trailing: switch (excerptLanguageLabel(excerpt)) {
                      final label? => Chip(label: Text(label)),
                      null => null,
                    },
                  ),
              ],
            ),
        ],
      ),
    );
  }
}
