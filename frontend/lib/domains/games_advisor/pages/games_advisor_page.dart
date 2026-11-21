import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../state/advisor_state.dart';
import '../state/game_card_text.dart';
import 'widgets/game_card.dart';

/// 空畫面的範例，點了直接送出（交接說明第 2 節）。
const _examples = ['我們 4 個人，想輕鬆聊天', '2 個人約會玩', '6 個人，30 分鐘內玩完'];

/// 推薦 Agent 正式頁面。所有操作都交給 `advisorProvider`，與參考畫面行為相同。
///
/// 網址可以帶 `?shop_id=<店家 id>`（例如從訂位頁進來）：這時店家沒有的桌遊，
/// 卡片上會多一行提示。
class GamesAdvisorPage extends ConsumerStatefulWidget {
  const GamesAdvisorPage({super.key, this.shopId});

  /// 從網址參數建立。
  factory GamesAdvisorPage.fromQuery(Map<String, String> query, {Key? key}) =>
      GamesAdvisorPage(key: key, shopId: advisorShopIdFromQuery(query));

  /// 玩家是從哪間店進來的；沒有店家時是 null。
  final String? shopId;

  @override
  ConsumerState<GamesAdvisorPage> createState() => _GamesAdvisorPageState();
}

class _GamesAdvisorPageState extends ConsumerState<GamesAdvisorPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// 這個頁面的對話：帶著網址給的店家。
  NotifierProvider<AdvisorNotifier, AdvisorState> get _provider =>
      advisorForShopProvider(widget.shopId);

  AdvisorNotifier get _advisor => ref.read(_provider.notifier);

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
    final state = ref.read(_provider);
    if (state.canSend) _advisor.sendMessage(state.draft);
    return KeyEventResult.handled;
  }

  /// 有新訊息時捲到最下面。
  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: kThemeAnimationDuration,
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // 送出時清空、失敗時放回：輸入框跟著 state 的 draft
    ref.listen(_provider.select((s) => s.draft), (_, draft) {
      if (_input.text != draft) _input.text = draft;
    });
    ref.listen(
      _provider.select((s) => (s.messages.length, s.status)),
      (_, _) => _scrollToEnd(),
    );
    final state = ref.watch(_provider);
    final sending = state.status == AdvisorStatus.sending;
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;

    return Scaffold(
      key: const Key('games-advisor-page'),
      appBar: AppBar(
        title: const Text('桌遊推薦'),
        actions: [
          OutlinedButton.icon(
            key: const Key('advisor-new'),
            onPressed: state.canStartNew ? _advisor.startNewConversation : null,
            icon: const Icon(Icons.refresh),
            label: const Text('開始新對話'),
          ),
          const SizedBox(width: AppSpacing.medium),
        ],
      ),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          key: const Key('advisor-column'),
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (state.notice case final notice?) _NoticeBanner(notice),
              Expanded(
                child: state.messages.isEmpty && !sending
                    ? _EmptyView(onExample: _advisor.sendMessage)
                    : _MessageList(
                        controller: _scroll,
                        messages: state.messages,
                        sending: sending,
                      ),
              ),
              _Composer(
                controller: _input,
                onKey: _onKey,
                sending: sending,
                canSend: state.canSend,
                draftLength: state.draftLength,
                onChanged: _advisor.editDraft,
                onSend: () => _advisor.sendMessage(state.draft),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NoticeBanner extends StatelessWidget {
  const _NoticeBanner(this.notice);

  final AdvisorNotice notice;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.small,
        AppSpacing.medium,
        0,
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.tertiaryContainer,
          borderRadius: BorderRadius.circular(AppRadius.button),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            children: [
              Icon(Icons.info_outline, color: scheme.onTertiaryContainer),
              const SizedBox(width: AppSpacing.small),
              Expanded(
                child: Text(
                  switch (notice) {
                    AdvisorNotice.expired => '對話已失效，請開始新對話',
                    AdvisorNotice.unavailable => '推薦 Agent 暫時無法回應，請再送一次',
                  },
                  style: Theme.of(context).textTheme.bodyMedium!.copyWith(
                    color: scheme.onTertiaryContainer,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView({required this.onExample});

  final void Function(String content) onExample;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.large),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: AppSpacing.xLarge),
          Icon(
            Icons.casino_outlined,
            size: AppSizes.emptyStateIcon,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: AppSpacing.large),
          Text(
            '我幫你挑桌遊',
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineMedium,
          ),
          const SizedBox(height: AppSpacing.small),
          Text(
            '告訴我幾個人、想玩多久、喜歡什麼感覺。',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge!.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.large),
          for (final example in _examples)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.small),
              child: OutlinedButton(
                onPressed: () => onExample(example),
                child: Text(example),
              ),
            ),
        ],
      ),
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.controller,
    required this.messages,
    required this.sending,
  });

  final ScrollController controller;
  final List<AdvisorChatMessage> messages;
  final bool sending;

  @override
  Widget build(BuildContext context) {
    return ListView(
      controller: controller,
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        for (final message in messages)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: switch (message) {
              PlayerMessage() => _PlayerBubble(message),
              AdvisorReplyMessage() => _AdvisorReply(message),
            },
          ),
        if (sending)
          const _AdvisorRow(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox.square(
                  dimension: AppSpacing.medium,
                  child: CircularProgressIndicator(),
                ),
                SizedBox(width: AppSpacing.small),
                Flexible(child: Text('正在找桌遊…')),
              ],
            ),
          ),
      ],
    );
  }
}

/// 玩家的訊息：靠右、主色底。
class _PlayerBubble extends StatelessWidget {
  const _PlayerBubble(this.message);

  final PlayerMessage message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: FractionallySizedBox(
        widthFactor: 0.8,
        alignment: Alignment.centerRight,
        child: Align(
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
                message.text,
                style: Theme.of(
                  context,
                ).textTheme.bodyLarge!.copyWith(color: scheme.onPrimary),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 推薦 Agent 那一側：左邊是頭像，右邊放內容。
class _AdvisorRow extends StatelessWidget {
  const _AdvisorRow({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: AppSizes.avatar / 2,
          backgroundColor: scheme.primaryContainer,
          foregroundColor: scheme.onPrimaryContainer,
          child: const Icon(Icons.casino_outlined),
        ),
        const SizedBox(width: AppSpacing.small),
        Flexible(
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(AppRadius.card),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.medium,
                vertical: AppSpacing.small,
              ),
              child: child,
            ),
          ),
        ),
      ],
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
        _AdvisorRow(
          child: Text(
            message.reply,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
        // 放寬提示：整則訊息一行，放在卡片上方
        if (relaxed != null && message.recommendations.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.medium),
            child: Align(
              alignment: Alignment.centerLeft,
              child: PillBadge(
                label: relaxedConstraintText(relaxed),
                tone: PillTone.duration,
                icon: Icons.tune,
              ),
            ),
          ),
        for (final recommendation in message.recommendations)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.medium),
            child: GameCard(recommendation),
          ),
      ],
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.onKey,
    required this.sending,
    required this.canSend,
    required this.draftLength,
    required this.onChanged,
    required this.onSend,
  });

  final TextEditingController controller;
  final FocusOnKeyEventCallback onKey;
  final bool sending;
  final bool canSend;
  final int draftLength;
  final ValueChanged<String> onChanged;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainer,
        border: Border(top: BorderSide(color: theme.colorScheme.outline)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Focus(
              onKeyEvent: onKey,
              child: TextField(
                key: const Key('advisor-input'),
                controller: controller,
                enabled: !sending,
                minLines: 1,
                maxLines: 4,
                keyboardType: TextInputType.multiline,
                onChanged: onChanged,
                decoration: InputDecoration(
                  hintText: '例如：我們 4 個人，想玩 1 小時內、輕鬆聊天的',
                  suffixIcon: Padding(
                    padding: const EdgeInsets.all(AppSpacing.xSmall),
                    child: IconButton.filled(
                      key: const Key('advisor-send'),
                      // 主題的圖示按鈕是深色圖示；主色底的送出鈕要用白色
                      style: ButtonStyle(
                        iconColor: WidgetStateProperty.resolveWith(
                          (states) => states.contains(WidgetState.disabled)
                              ? theme.colorScheme.onSurfaceVariant
                              : theme.colorScheme.onPrimary,
                        ),
                      ),
                      tooltip: '送出',
                      onPressed: canSend ? onSend : null,
                      icon: const Icon(Icons.send),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: AppSpacing.small,
              children: [
                Text(
                  '$draftLength / $advisorMaxContentLength 字'
                  '（Enter 送出、Shift+Enter 換行）',
                  style: theme.textTheme.bodySmall,
                ),
                // rules_qa 還沒有正式頁面，先停用；有頁面後改成連過去
                const TextButton(onPressed: null, child: Text('想問規則或玩法？到規則問答')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
