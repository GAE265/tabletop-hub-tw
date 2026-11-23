import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/game_match.dart';
import '../state/match_current_user.dart';
import '../state/match_detail_state.dart';
import '../state/match_labels.dart';
import '../state/white_rose.dart';
import 'widgets/match_widgets.dart';
import 'widgets/result_form_card.dart';
import 'widgets/turn_form_card.dart';

/// 一局（`/matches/<id>`）：資料與統計、參加者、回合紀錄、結果與確認。
///
/// Stitch 版面：木紋背景，每個區塊一張有厚度的卡片；手機的浮動導覽列蓋住的高度留在最下面。
/// 沒有即時推送：其他人記錄的內容按右上角「重新整理」取得。
class MatchDetailPage extends ConsumerWidget {
  const MatchDetailPage({required this.matchId, super.key});

  final String matchId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(matchDetailProvider(matchId));
    final notifier = ref.read(matchDetailProvider(matchId).notifier);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    final body = state.match.when(
      loading: () => const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: AppSpacing.small),
            Text('載入中…'),
          ],
        ),
      ),
      error: (error, _) => Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: ThickCard(
            child: Padding(
              padding: matchCardInset,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('載入失敗：${matchErrorText(error)}'),
                  const SizedBox(height: AppSpacing.small),
                  ThickButton(
                    buttonKey: const Key('match-retry'),
                    style: ThickStyle.primary,
                    icon: Icons.refresh,
                    label: '重試',
                    shadow: AppShadows.soft,
                    onPressed: notifier.reload,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      data: (match) => Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: _Body(matchId: matchId, match: match, state: state),
        ),
      ),
    );
    return Scaffold(
      key: const Key('match-detail-page'),
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        // 放在木紋上，用半透明白底，文字才看得清楚
        backgroundColor: AppColors.headerGlass,
        leading: IconButton(
          key: const Key('match-back'),
          tooltip: '回到戰績',
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/matches'),
        ),
        title: const Text('一局'),
        actions: [
          IconButton(
            key: const Key('match-refresh'),
            tooltip: '重新整理',
            icon: const Icon(Icons.refresh),
            onPressed: state.refreshing ? null : notifier.reload,
          ),
        ],
      ),
      body: WoodBackground.isPaintedAbove(context)
          ? body
          : WoodBackground(child: body),
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({
    required this.matchId,
    required this.match,
    required this.state,
  });

  final String matchId;
  final GameMatch match;
  final MatchDetailState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(matchUserIdProvider);
    final isParticipant = state.mine(userId) != null;
    final canConfirm = state.actionsFor(userId).contains(MatchAction.confirm);
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final notifier = ref.read(matchDetailProvider(matchId).notifier);
    const gap = SizedBox(height: AppSpacing.medium);
    // 進度條固定在列表上方，捲到哪裡都看得到
    return Column(
      children: [
        if (state.refreshing || state.busy)
          const LinearProgressIndicator(key: Key('match-busy')),
        Expanded(
          // 區塊不多，一次建好（不用延遲建立的 ListView），捲到哪裡都不會重建表單
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(
              AppSpacing.medium,
              AppSpacing.medium,
              AppSpacing.medium,
              AppSpacing.medium + bottomInset,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _InfoCard(match: match, state: state),
                gap,
                _ParticipantsCard(matchId: matchId, match: match, state: state),
                gap,
                MatchSection(
                  title: '回合紀錄',
                  icon: Icons.format_list_numbered,
                  children: [
                    if (match.turns.isEmpty)
                      const Text('還沒有回合紀錄（回合紀錄是選填的，只記結果也可以）')
                    else
                      for (final (i, turn) in match.turns.indexed) ...[
                        if (i > 0) const SizedBox(height: AppSpacing.small),
                        _TurnTile(turn: turn),
                      ],
                    if (isParticipant) ...[
                      const Divider(height: AppSpacing.xLarge),
                      TurnFormCard(matchId: matchId, match: match),
                    ],
                  ],
                ),
                gap,
                MatchSection(
                  title: '結果',
                  icon: Icons.emoji_events_outlined,
                  children: [
                    if (isParticipant)
                      ResultFormCard(matchId: matchId, match: match)
                    else
                      const Text(
                        '只有這一局的參加者可以記錄結果',
                        key: Key('result-readonly'),
                      ),
                    if (canConfirm) ...[
                      const SizedBox(height: AppSpacing.medium),
                      ThickButton(
                        buttonKey: const Key('confirm'),
                        style: ThickStyle.primary,
                        icon: Icons.verified_outlined,
                        label: '確認這局的紀錄',
                        expand: true,
                        onPressed: state.busy ? null : notifier.confirmMine,
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// 這一局的資料：狀態、第幾回合、幾人對局、複製編號；遊戲名稱、日期、地點、開局者、結果與統計。
class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.match, required this.state});

  final GameMatch match;
  final MatchDetailState state;

  Future<void> _copyId(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: match.id));
    if (!context.mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('已複製局的編號')));
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final winning = match.result?['winning_faction'] as String?;
    final muted = textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted);
    final lastTurn = match.turns.isEmpty
        ? null
        : match.turns.map((t) => t.turnNumber).reduce((a, b) => a > b ? a : b);
    return ThickCard(
      key: const Key('match-info'),
      child: Padding(
        padding: matchCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Wrap(
                    spacing: AppSpacing.small,
                    runSpacing: AppSpacing.small,
                    children: [
                      PillBadge(
                        label: statusLabel(match.status),
                        tone: match.status == 'in_progress'
                            ? PillTone.duration
                            : PillTone.neutral,
                      ),
                      if (lastTurn != null)
                        PillBadge(
                          label: '第 $lastTurn 回合',
                          tone: PillTone.accent,
                        ),
                      PillBadge(
                        label: '${match.participantCount} 人對局',
                        tone: PillTone.players,
                        icon: Icons.group_outlined,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.small),
                ThickIconButton(
                  key: const Key('match-copy-id'),
                  tooltip: '複製局的編號',
                  icon: const Icon(Icons.copy_outlined, color: AppColors.ink),
                  onPressed: () => _copyId(context),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '編號 ${match.id}',
              style: textTheme.bodySmall!.copyWith(color: AppColors.inkMuted),
            ),
            Text(
              match.game.name,
              style: textTheme.headlineSmall!.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: AppSpacing.small),
            IconText(
              icon: Icons.calendar_today_outlined,
              text: formatPlayedOn(match.playedOn),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            IconText(
              icon: match.locationType == 'shop'
                  ? Icons.storefront_outlined
                  : Icons.home_outlined,
              text: matchLocationText(match),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            IconText(
              icon: Icons.person_outline,
              text: '開局者：${match.createdBy.displayName}',
            ),
            const SizedBox(height: AppSpacing.medium),
            const DashedLine(),
            const SizedBox(height: AppSpacing.medium),
            Text(
              winning == null ? '結果：尚未記錄' : '結果：${factionLabel(winning)}獲勝',
              style: textTheme.titleMedium!.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text(
              state.participantSummary!,
              key: const Key('match-summary'),
              style: muted,
            ),
            const SizedBox(height: AppSpacing.small),
            PillBadge(
              label: state.validityLabel!,
              tone: match.isValid ? PillTone.players : PillTone.accent,
            ),
          ],
        ),
      ),
    );
  }
}

class _ParticipantsCard extends ConsumerStatefulWidget {
  const _ParticipantsCard({
    required this.matchId,
    required this.match,
    required this.state,
  });

  final String matchId;
  final GameMatch match;
  final MatchDetailState state;

  @override
  ConsumerState<_ParticipantsCard> createState() => _ParticipantsCardState();
}

class _ParticipantsCardState extends ConsumerState<_ParticipantsCard> {
  final _joinSeat = TextEditingController();
  final _name = TextEditingController();
  final _nameSeat = TextEditingController();

  MatchDetailNotifier get _n =>
      ref.read(matchDetailProvider(widget.matchId).notifier);

  @override
  void dispose() {
    _joinSeat.dispose();
    _name.dispose();
    _nameSeat.dispose();
    super.dispose();
  }

  int? _int(TextEditingController c) => int.tryParse(c.text.trim());

  Future<void> _addNamed() async {
    await _n.addNamed(_name.text, seatNumber: _int(_nameSeat));
    if (!mounted) return;
    if (ref.read(matchDetailProvider(widget.matchId)).error == null) {
      _name.clear();
      _nameSeat.clear();
    }
  }

  Future<void> _remove(MatchParticipant participant, bool isMe) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(isMe ? '退出這一局' : '移除參加者'),
        content: Text(
          isMe
              ? '要退出這一局（座位 ${participant.seatNumber}）嗎？'
              : '要移除座位 ${participant.seatNumber}「${participant.displayName}」嗎？',
        ),
        actions: [
          TextButton(
            key: const Key('remove-cancel'),
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            key: const Key('remove-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: Text(isMe ? '退出' : '移除'),
          ),
        ],
      ),
    );
    if (ok ?? false) await _n.remove(participant.id);
  }

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(matchUserIdProvider);
    final state = widget.state;
    final busy = state.busy;
    final actions = state.actionsFor(userId);
    final canRemove = state.canManageParticipants(userId);
    final me = state.mine(userId);
    final text = Theme.of(context).textTheme;
    return MatchSection(
      title: '參加者',
      icon: Icons.groups_outlined,
      children: [
        for (final (i, p) in widget.match.participants.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.small),
          _ParticipantRow(
            participant: p,
            isMe: p.userId != null && p.userId == userId,
            // 自己用下面的「退出這一局」
            onRemove: canRemove && p.id != me?.id
                ? (busy ? null : () => _remove(p, false))
                : null,
            showRemove: canRemove && p.id != me?.id,
          ),
        ],
        if (actions.contains(MatchAction.join)) ...[
          const SizedBox(height: AppSpacing.medium),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('join-seat'),
                  controller: _joinSeat,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: '我的座位（選填）'),
                ),
              ),
              const SizedBox(width: AppSpacing.small),
              ThickButton(
                buttonKey: const Key('join'),
                style: ThickStyle.primary,
                icon: Icons.person_add_alt_1_outlined,
                label: '加入這一局',
                shadow: AppShadows.soft,
                onPressed: busy
                    ? null
                    : () => _n.joinSelf(seatNumber: _int(_joinSeat)),
              ),
            ],
          ),
        ],
        if (actions.contains(MatchAction.addNamed)) ...[
          const SizedBox(height: AppSpacing.medium),
          Container(
            padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
            decoration: BoxDecoration(
              color: AppColors.backgroundAlt,
              border: Border.all(color: AppColors.cardEdge),
              borderRadius: BorderRadius.circular(AppRadius.button),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '新增沒有帳號的人',
                  style: text.titleSmall!.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: AppSpacing.small),
                Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextField(
                        key: const Key('add-named-name'),
                        controller: _name,
                        decoration: const InputDecoration(
                          labelText: '名字（例如 Amy）',
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.small),
                    Expanded(
                      child: TextField(
                        key: const Key('add-named-seat'),
                        controller: _nameSeat,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: '座位（選填）'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.small),
                Align(
                  alignment: Alignment.centerLeft,
                  child: ThickButton(
                    buttonKey: const Key('add-named'),
                    style: ThickStyle.light,
                    icon: Icons.person_add_alt_outlined,
                    label: '新增',
                    shadow: AppShadows.soft,
                    onPressed: busy ? null : _addNamed,
                  ),
                ),
              ],
            ),
          ),
        ],
        if (actions.contains(MatchAction.leave) && me != null) ...[
          const SizedBox(height: AppSpacing.small),
          Align(
            alignment: Alignment.centerRight,
            child: ThickButton(
              buttonKey: const Key('leave'),
              style: ThickStyle.light,
              icon: Icons.logout,
              label: '退出這一局',
              shadow: AppShadows.soft,
              onPressed: busy ? null : () => _remove(me, true),
            ),
          ),
        ],
        // 加入、新增、移除、確認的結果顯示在按鈕旁邊
        if (state.message case final message?) ...[
          const SizedBox(height: AppSpacing.small),
          MatchBanner(key: const Key('match-message'), text: message),
        ],
        if (state.error case final error?) ...[
          const SizedBox(height: AppSpacing.small),
          MatchBanner(
            key: const Key('match-error'),
            text: matchErrorText(error),
            isError: true,
          ),
        ],
      ],
    );
  }
}

/// 參加者一列：頭像（右下角座位）、名字與有沒有帳號、座位與陣營；
/// 右邊是分數、獲勝與確認狀態（沒有帳號的人不用確認）。自己的一列是淡橘底。
class _ParticipantRow extends StatelessWidget {
  const _ParticipantRow({
    required this.participant,
    required this.isMe,
    required this.onRemove,
    required this.showRemove,
  });

  final MatchParticipant participant;
  final bool isMe;
  final VoidCallback? onRemove;
  final bool showRemove;

  @override
  Widget build(BuildContext context) {
    final p = participant;
    final hasAccount = p.userId != null;
    final text = Theme.of(context).textTheme;
    final details = [
      '座位 ${p.seatNumber}',
      '陣營：${factionLabel(p.faction)}',
      if (p.isWinner == false) '落敗',
    ].join('・');
    return Container(
      key: Key('participant-${p.id}'),
      padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
      decoration: BoxDecoration(
        color: isMe ? AppColors.primaryTint : AppColors.backgroundAlt,
        border: Border.all(color: AppColors.cardEdge),
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Row(
        children: [
          _SeatAvatar(participant: p, isMe: isMe),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: AppSpacing.small,
                  runSpacing: AppSpacing.xSmall,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      '${p.displayName}${isMe ? '（我）' : ''}',
                      style: text.titleSmall!.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    PillBadge(label: hasAccount ? '有帳號' : '沒有帳號'),
                  ],
                ),
                const SizedBox(height: AppSpacing.xSmall),
                Text(
                  details,
                  style: text.bodySmall!.copyWith(color: AppColors.inkMuted),
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.small),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (p.score case final score?)
                Text(
                  '$score 分',
                  style: text.titleMedium!.copyWith(
                    color: AppColors.primaryText,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              if (p.isWinner == true)
                const PillBadge(
                  label: '獲勝',
                  tone: PillTone.accent,
                  icon: Icons.emoji_events_outlined,
                ),
              if (hasAccount)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      p.isConfirmed
                          ? Icons.check_circle
                          : Icons.hourglass_empty,
                      size: AppSizes.inlineIcon,
                      color: p.isConfirmed ? AppColors.sage : AppColors.amber,
                    ),
                    const SizedBox(width: AppSpacing.xSmall),
                    Text(
                      p.isConfirmed ? '已確認' : '尚未確認',
                      style: text.bodySmall!.copyWith(
                        color: p.isConfirmed
                            ? AppColors.sage
                            : AppColors.amberText,
                      ),
                    ),
                  ],
                ),
            ],
          ),
          if (showRemove)
            IconButton(
              key: Key('remove-${p.id}'),
              tooltip: '移除',
              icon: const Icon(Icons.person_remove_outlined),
              onPressed: onRemove,
            ),
        ],
      ),
    );
  }
}

/// 頭像：名字的第一個字，右下角深色小圓寫座位。
class _SeatAvatar extends StatelessWidget {
  const _SeatAvatar({required this.participant, required this.isMe});

  final MatchParticipant participant;
  final bool isMe;

  @override
  Widget build(BuildContext context) {
    final p = participant;
    final color = isMe
        ? AppColors.primary
        : p.userId != null
        ? AppColors.sage
        : AppColors.inkMuted;
    return SizedBox(
      width: AppSizes.avatar + AppSpacing.xSmall,
      height: AppSizes.avatar + AppSpacing.xSmall,
      child: Stack(
        children: [
          CircleAvatar(
            radius: AppSizes.avatar / 2,
            backgroundColor: color,
            foregroundColor: AppColors.surface,
            child: Text(
              p.displayName.isEmpty ? '？' : p.displayName.characters.first,
            ),
          ),
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              width: AppSizes.seatBadge,
              height: AppSizes.seatBadge,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.ink,
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.surface),
              ),
              child: Text(
                '${p.seatNumber}',
                style: Theme.of(context).textTheme.labelSmall!.copyWith(
                  color: AppColors.surface,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 一個回合的小卡：標題（第幾回合、首家）、出牌座位，數量與白薔薇用膠囊。
class _TurnTile extends StatelessWidget {
  const _TurnTile({required this.turn});

  final MatchTurn turn;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final chips = turnChips(turn.gameData);
    return Container(
      key: Key('turn-${turn.turnNumber}'),
      padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
      decoration: BoxDecoration(
        color: AppColors.backgroundAlt,
        border: Border.all(color: AppColors.cardEdge),
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            turnTitle(turn),
            style: text.titleSmall!.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: AppSpacing.xSmall),
          Text(
            turnPlayedText(turn.gameData),
            style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
          ),
          if (chips.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.small),
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.small,
              children: [
                for (final chip in chips)
                  PillBadge(
                    label: chip,
                    tone: chip == '白薔薇' ? PillTone.accent : PillTone.neutral,
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
