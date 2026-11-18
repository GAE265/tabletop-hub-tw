import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
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
    return Scaffold(
      key: const Key('match-detail-page'),
      appBar: AppBar(
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
      body: state.match.when(
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
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('載入失敗：${matchErrorText(error)}'),
                const SizedBox(height: AppSpacing.small),
                FilledButton(
                  key: const Key('match-retry'),
                  onPressed: notifier.reload,
                  child: const Text('重試'),
                ),
              ],
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
      ),
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
    const gap = SizedBox(height: AppSpacing.medium);
    // 進度條固定在列表上方，捲到哪裡都看得到
    return Column(
      children: [
        if (state.refreshing || state.busy)
          const LinearProgressIndicator(key: Key('match-busy')),
        Expanded(child: _list(isParticipant, gap)),
      ],
    );
  }

  Widget _list(bool isParticipant, Widget gap) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        _InfoCard(match: match, state: state),
        gap,
        _ParticipantsCard(matchId: matchId, match: match, state: state),
        gap,
        MatchSection(
          title: '回合紀錄',
          children: [
            if (match.turns.isEmpty)
              const Text('還沒有回合紀錄（回合紀錄是選填的，只記結果也可以）')
            else
              for (final turn in match.turns)
                ListTile(
                  key: Key('turn-${turn.turnNumber}'),
                  contentPadding: EdgeInsets.zero,
                  title: Text(turnTitle(turn)),
                  subtitle: Text(turnDetail(turn.gameData)),
                ),
            if (isParticipant) ...[
              const Divider(height: AppSpacing.large),
              TurnFormCard(matchId: matchId, match: match),
            ],
          ],
        ),
        gap,
        MatchSection(
          title: '結果',
          children: [
            if (isParticipant)
              ResultFormCard(matchId: matchId, match: match)
            else
              const Text('只有這一局的參加者可以記錄結果', key: Key('result-readonly')),
          ],
        ),
      ],
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.match, required this.state});

  final GameMatch match;
  final MatchDetailState state;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final winning = match.result?['winning_faction'] as String?;
    final muted = textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted);
    return Card(
      key: const Key('match-info'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              match.game.name,
              style: textTheme.titleLarge!.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: AppSpacing.small),
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.small,
              children: [
                PillBadge(
                  label: statusLabel(match.status),
                  tone: match.status == 'in_progress'
                      ? PillTone.duration
                      : PillTone.neutral,
                ),
                PillBadge(label: matchLocationText(match)),
                PillBadge(
                  label: state.validityLabel!,
                  tone: match.isValid ? PillTone.players : PillTone.accent,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(formatPlayedOn(match.playedOn), style: muted),
            Text('開局者：${match.createdBy.displayName}', style: muted),
            Text(
              winning == null ? '結果：尚未記錄' : '結果：${factionLabel(winning)}獲勝',
              style: textTheme.bodyLarge!.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text(
              state.participantSummary!,
              key: const Key('match-summary'),
              style: muted,
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
    final muted = Theme.of(
      context,
    ).textTheme.bodySmall!.copyWith(color: AppColors.inkMuted);
    return MatchSection(
      title: '參加者',
      children: [
        for (final p in widget.match.participants)
          _participantTile(p, userId, canRemove, busy, muted),
        if (actions.contains(MatchAction.join)) ...[
          const SizedBox(height: AppSpacing.small),
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
              FilledButton.icon(
                key: const Key('join'),
                onPressed: busy
                    ? null
                    : () => _n.joinSelf(seatNumber: _int(_joinSeat)),
                icon: const Icon(Icons.person_add_alt_1_outlined),
                label: const Text('加入這一局'),
              ),
            ],
          ),
        ],
        if (actions.contains(MatchAction.addNamed)) ...[
          const SizedBox(height: AppSpacing.small),
          Text('新增沒有帳號的人', style: muted),
          const SizedBox(height: AppSpacing.xSmall),
          Row(
            children: [
              Expanded(
                flex: 2,
                child: TextField(
                  key: const Key('add-named-name'),
                  controller: _name,
                  decoration: const InputDecoration(labelText: '名字（例如 Amy）'),
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
            child: OutlinedButton.icon(
              key: const Key('add-named'),
              onPressed: busy ? null : _addNamed,
              icon: const Icon(Icons.add),
              label: const Text('新增'),
            ),
          ),
        ],
        if (actions.contains(MatchAction.confirm)) ...[
          const SizedBox(height: AppSpacing.small),
          FilledButton.icon(
            key: const Key('confirm'),
            onPressed: busy ? null : _n.confirmMine,
            icon: const Icon(Icons.verified_outlined),
            label: const Text('確認這局的紀錄'),
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

  Widget _participantTile(
    MatchParticipant p,
    String? userId,
    bool canRemove,
    bool busy,
    TextStyle muted,
  ) {
    final isMe = p.userId != null && p.userId == userId;
    final hasAccount = p.userId != null;
    final details = [
      '座位 ${p.seatNumber}',
      hasAccount ? '有帳號' : '沒有帳號',
      '陣營：${factionLabel(p.faction)}',
      if (p.isWinner != null) p.isWinner! ? '獲勝' : '落敗',
      if (hasAccount) p.isConfirmed ? '已確認' : '尚未確認',
    ].join('・');
    return ListTile(
      key: Key('participant-${p.id}'),
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(child: Text('${p.seatNumber}')),
      title: Text('${p.displayName}${isMe ? '（我）' : ''}'),
      subtitle: Text(details, style: muted),
      trailing: canRemove
          ? IconButton(
              key: Key('remove-${p.id}'),
              tooltip: isMe ? '退出' : '移除',
              icon: const Icon(Icons.person_remove_outlined),
              onPressed: busy ? null : () => _remove(p, isMe),
            )
          : null,
    );
  }
}
