import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/chat_widgets.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/size_reporter.dart';
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
///
/// Stitch 版面（docs/ui/stitch/）：木紋背景，文字放在卡片或泡泡裡；
/// 手機的浮動導覽列蓋住的高度（MediaQuery 底部 padding）留在輸入區下方。
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

  /// 輸入區的高度：對話內容最下面要留出這麼多，捲到底時才不會被輸入區蓋住。
  double _composerHeight = 0;

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

    final column = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        key: const Key('advisor-column'),
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.medium,
                AppSpacing.medium,
                AppSpacing.medium,
                0,
              ),
              child: _Header(
                canStartNew: state.canStartNew,
                onStartNew: _advisor.startNewConversation,
              ),
            ),
            if (state.notice case final notice?) _NoticeBanner(notice),
            // 輸入區浮在對話上面：內容從輸入區後面滑過去，不會在上緣被切成一條線
            Expanded(
              child: Stack(
                children: [
                  Positioned.fill(
                    child: TopEdgeFade(
                      key: const Key('advisor-scroll-fade'),
                      child: state.messages.isEmpty && !sending
                          ? _EmptyView(
                              onExample: _advisor.sendMessage,
                              bottomSpace: _composerHeight,
                            )
                          : _MessageList(
                              controller: _scroll,
                              messages: state.messages,
                              sending: sending,
                              bottomSpace: _composerHeight,
                            ),
                    ),
                  ),
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: SizeReporter(
                      onHeight: (height) {
                        if (height != _composerHeight) {
                          setState(() => _composerHeight = height);
                        }
                      },
                      child: _Composer(
                        controller: _input,
                        onKey: _onKey,
                        sending: sending,
                        canSend: state.canSend,
                        draftLength: state.draftLength,
                        onChanged: _advisor.editDraft,
                        onSend: () => _advisor.sendMessage(state.draft),
                        bottomInset: MediaQuery.paddingOf(context).bottom,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );

    return Scaffold(
      key: const Key('games-advisor-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? column
            : WoodBackground(child: column),
      ),
    );
  }
}

/// 頁首白底條：標題與「開始新對話」。
class _Header extends StatelessWidget {
  const _Header({required this.canStartNew, required this.onStartNew});

  final bool canStartNew;
  final VoidCallback onStartNew;

  @override
  Widget build(BuildContext context) {
    return GlassBar(
      key: const Key('advisor-header'),
      child: Row(
        children: [
          const Icon(Icons.auto_awesome_outlined, color: AppColors.primaryText),
          const SizedBox(width: AppSpacing.small),
          Expanded(
            child: Text(
              '桌遊推薦',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          OutlinedButton.icon(
            key: const Key('advisor-new'),
            style: OutlinedButton.styleFrom(shape: const StadiumBorder()),
            onPressed: canStartNew ? onStartNew : null,
            icon: const Icon(Icons.refresh),
            label: const Text('開始新對話'),
          ),
        ],
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
  const _EmptyView({required this.onExample, required this.bottomSpace});

  final void Function(String content) onExample;

  /// 最下面要留出的空間（浮在上面的輸入區高度）。
  final double bottomSpace;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.medium,
        AppSpacing.medium,
        bottomSpace,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 空畫面就是推薦助理的第一句話，和之後的對話同一個樣子
          AssistantMessage(
            name: '推薦助理',
            bubbleKey: const Key('advisor-empty'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '我幫你挑桌遊',
                  style: text.titleMedium!.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpacing.xSmall),
                Text('告訴我幾個人、想玩多久、喜歡什麼感覺。', style: text.bodyLarge),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
          // 範例像聊天 App 的「建議回覆」，點了直接送出
          Wrap(
            spacing: AppSpacing.small,
            runSpacing: AppSpacing.small + AppSpacing.xSmall,
            children: [
              for (final example in _examples)
                SuggestionChip(label: example, onTap: () => onExample(example)),
            ],
          ),
          const SizedBox(height: AppSpacing.large),
          const _RulesLink(),
        ],
      ),
    );
  }
}

/// 到規則問答的連結卡片（`/rules`）。
class _RulesLink extends StatelessWidget {
  const _RulesLink();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('advisor-rules-link'),
      onTap: () => context.go('/rules'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Row(
          children: [
            Container(
              width: AppSizes.avatar,
              height: AppSizes.avatar,
              decoration: BoxDecoration(
                color: AppColors.amberTint,
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
              child: const Icon(
                Icons.menu_book_outlined,
                color: AppColors.amberText,
              ),
            ),
            const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('想問規則或玩法？到規則問答', style: text.titleSmall),
                  Text('看教學影片、隨時問規則', style: text.bodySmall),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward, color: AppColors.primaryText),
          ],
        ),
      ),
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.controller,
    required this.messages,
    required this.sending,
    required this.bottomSpace,
  });

  final ScrollController controller;
  final List<AdvisorChatMessage> messages;
  final bool sending;

  /// 最下面要留出的空間（浮在上面的輸入區高度）。
  final double bottomSpace;

  @override
  Widget build(BuildContext context) {
    return ListView(
      controller: controller,
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.medium,
        AppSpacing.medium,
        bottomSpace,
      ),
      children: [
        for (final message in messages)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: switch (message) {
              PlayerMessage() => UserBubble(text: message.text),
              AdvisorReplyMessage() => _AdvisorReply(message),
            },
          ),
        if (sending) const ThinkingPill(text: '正在找桌遊…'),
        const SizedBox(height: AppSpacing.small),
        const _RulesLink(),
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
        AssistantMessage(
          name: '推薦助理',
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
    required this.bottomInset,
  });

  final TextEditingController controller;
  final FocusOnKeyEventCallback onKey;
  final bool sending;
  final bool canSend;
  final int draftLength;
  final ValueChanged<String> onChanged;
  final VoidCallback onSend;

  /// 手機浮動導覽列蓋住的高度：輸入區要停在它上方。
  final double bottomInset;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.small,
        AppSpacing.medium,
        AppSpacing.medium + bottomInset,
      ),
      child: ThickCard(
        key: const Key('advisor-composer'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
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
                    '$draftLength / $advisorMaxContentLength 字',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
