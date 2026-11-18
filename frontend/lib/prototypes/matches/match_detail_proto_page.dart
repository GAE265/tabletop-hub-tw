import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domains/matches/data/game_match.dart';
import '../../domains/matches/state/match_current_user.dart';
import '../../domains/matches/state/match_detail_state.dart';
import '../../domains/matches/state/match_labels.dart';
import '../../domains/matches/state/white_rose.dart';
import 'matches_proto_page.dart' show errorText;
import 'proto_widgets.dart';
import 'result_form_section.dart';
import 'turn_form_section.dart';

/// 一局的參考畫面：資料、參加者、回合紀錄與表單、結果與確認。
///
/// 其他人要看最新內容就按右上角的重新整理（不做即時推送）。
class MatchDetailProtoPage extends ConsumerWidget {
  const MatchDetailProtoPage({required this.matchId, super.key});

  final String matchId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(matchDetailProvider(matchId));
    final notifier = ref.read(matchDetailProvider(matchId).notifier);

    return Scaffold(
      key: const Key('match-detail-proto-page'),
      appBar: AppBar(
        leading: IconButton(
          key: const Key('back'),
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/proto/matches'),
        ),
        title: const Text('一局（參考畫面）'),
        actions: [
          IconButton(
            key: const Key('refresh'),
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
              CircularProgressIndicator(key: Key('loading')),
              Text('載入中…'),
            ],
          ),
        ),
        error: (e, _) => Center(
          child: Column(
            key: const Key('load-error'),
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('載入失敗：${errorText(e)}'),
              FilledButton(
                key: const Key('retry'),
                onPressed: notifier.reload,
                child: const Text('重試'),
              ),
            ],
          ),
        ),
        data: (match) => _Body(matchId: matchId, match: match, state: state),
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
    final notifier = ref.read(matchDetailProvider(matchId).notifier);
    final actions = state.actionsFor(userId);
    final isParticipant = state.mine(userId) != null;
    final winning = match.result?['winning_faction'] as String?;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (state.refreshing || state.busy)
          const LinearProgressIndicator(key: Key('busy')),
        Card(
          child: ListTile(
            title: Text('${match.game.name}　${formatDate(match.playedOn)}'),
            subtitle: Text(
              '${statusLabel(match.status)}・${locationLabel(match.locationType)}'
              '${match.shop == null ? '' : '（${match.shop!.name}）'}\n'
              '開局者：${match.createdBy.displayName}\n'
              '結果：${winning == null ? '尚未記錄' : '${factionLabel(winning)}獲勝'}',
            ),
            isThreeLine: true,
          ),
        ),
        Text(state.participantSummary!, key: const Key('participant-summary')),
        Text(state.validityLabel!, key: const Key('validity')),
        if (state.message != null) SuccessLine(state.message!),
        if (state.error != null) ErrorLine(state.error!),
        const Divider(),
        const Text('參加者', style: TextStyle(fontWeight: FontWeight.bold)),
        for (final p in match.participants)
          _ParticipantTile(
            participant: p,
            isMe: p.userId != null && p.userId == userId,
            canRemove: state.canManageParticipants(userId),
            busy: state.busy,
            onRemove: () => _confirmRemove(context, p, notifier),
          ),
        _ActionBar(
          matchId: matchId,
          actions: actions,
          state: state,
          notifier: notifier,
        ),
        const Divider(),
        const Text('回合紀錄', style: TextStyle(fontWeight: FontWeight.bold)),
        if (match.turns.isEmpty)
          const Text('還沒有回合紀錄（回合紀錄是選填的，只記結果也可以）', key: Key('turns-empty')),
        for (final t in match.turns) _TurnTile(turn: t),
        if (isParticipant) TurnFormSection(matchId: matchId, match: match),
        const Divider(),
        const Text('結果', style: TextStyle(fontWeight: FontWeight.bold)),
        if (isParticipant)
          ResultFormSection(matchId: matchId, match: match)
        else
          const Text('只有這一局的參加者可以記錄結果', key: Key('result-readonly')),
      ],
    );
  }

  Future<void> _confirmRemove(
    BuildContext context,
    MatchParticipant participant,
    MatchDetailNotifier notifier,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('移除參加者'),
        content: Text(
          '要移除座位 ${participant.seatNumber}「${participant.displayName}」嗎？',
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
            child: const Text('移除'),
          ),
        ],
      ),
    );
    if (confirmed == true) await notifier.remove(participant.id);
  }
}

class _ParticipantTile extends StatelessWidget {
  const _ParticipantTile({
    required this.participant,
    required this.isMe,
    required this.canRemove,
    required this.busy,
    required this.onRemove,
  });

  final MatchParticipant participant;
  final bool isMe;
  final bool canRemove;
  final bool busy;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final p = participant;
    final winner = p.isWinner == null ? '' : (p.isWinner! ? '・獲勝' : '・落敗');
    return ListTile(
      key: Key('participant-${p.id}'),
      title: Text('座位 ${p.seatNumber}　${p.displayName}${isMe ? '（我）' : ''}'),
      subtitle: Text(
        '${p.userId == null ? '沒有帳號' : '有帳號'}・陣營：${factionLabel(p.faction)}$winner'
        '${p.userId == null ? '' : (p.isConfirmed ? '・已確認' : '・尚未確認')}',
      ),
      trailing: canRemove
          ? IconButton(
              key: Key('remove-${p.id}'),
              tooltip: isMe ? '退出' : '移除',
              icon: const Icon(Icons.person_remove),
              onPressed: busy ? null : onRemove,
            )
          : null,
    );
  }
}

class _TurnTile extends StatelessWidget {
  const _TurnTile({required this.turn});

  final MatchTurn turn;

  @override
  Widget build(BuildContext context) {
    final d = turn.gameData;
    return ListTile(
      key: Key('turn-${turn.turnNumber}'),
      title: Text('第 ${turn.turnNumber} 回合　主導：座位 ${turn.seatNumber}'),
      subtitle: Text(
        '出牌座位：${(d['played_seat_numbers'] as List?)?.join('、') ?? '-'}　'
        '雙刃 ${d['double_blade_count']}・暗刃 ${d['dark_blade_count']}・'
        '巨刃 ${d['giant_blade_count']}・信者 ${d['faithful_count']}・'
        '白薔薇：${d['has_white_rose'] == true ? '有' : '沒有'}',
      ),
    );
  }
}

class _ActionBar extends ConsumerStatefulWidget {
  const _ActionBar({
    required this.matchId,
    required this.actions,
    required this.state,
    required this.notifier,
  });

  final String matchId;
  final List<MatchAction> actions;
  final MatchDetailState state;
  final MatchDetailNotifier notifier;

  @override
  ConsumerState<_ActionBar> createState() => _ActionBarState();
}

class _ActionBarState extends ConsumerState<_ActionBar> {
  final _seat = TextEditingController();
  final _name = TextEditingController();
  final _nameSeat = TextEditingController();

  @override
  void dispose() {
    _seat.dispose();
    _name.dispose();
    _nameSeat.dispose();
    super.dispose();
  }

  int? _int(TextEditingController c) => int.tryParse(c.text.trim());

  @override
  Widget build(BuildContext context) {
    final busy = widget.state.busy;
    final notifier = widget.notifier;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.actions.contains(MatchAction.join)) ...[
          TextField(
            key: const Key('join-seat'),
            controller: _seat,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '我的座位（選填）'),
          ),
          FilledButton(
            key: const Key('join'),
            onPressed: busy
                ? null
                : () => notifier.joinSelf(seatNumber: _int(_seat)),
            child: const Text('加入這一局'),
          ),
        ],
        if (widget.actions.contains(MatchAction.addNamed)) ...[
          const Text('新增沒有帳號的人'),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('add-named-name'),
                  controller: _name,
                  decoration: const InputDecoration(labelText: '名字（例如 Amy）'),
                ),
              ),
              SizedBox(
                width: 120,
                child: TextField(
                  key: const Key('add-named-seat'),
                  controller: _nameSeat,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: '座位（選填）'),
                ),
              ),
            ],
          ),
          OutlinedButton(
            key: const Key('add-named'),
            onPressed: busy
                ? null
                : () async {
                    await notifier.addNamed(
                      _name.text,
                      seatNumber: _int(_nameSeat),
                    );
                    if (ref.read(matchDetailProvider(widget.matchId)).error ==
                        null) {
                      _name.clear();
                      _nameSeat.clear();
                    }
                  },
            child: const Text('新增'),
          ),
        ],
        if (widget.actions.contains(MatchAction.confirm))
          FilledButton(
            key: const Key('confirm'),
            onPressed: busy ? null : notifier.confirmMine,
            child: const Text('確認這局的紀錄'),
          ),
      ],
    );
  }
}
