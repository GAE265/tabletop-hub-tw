import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/matches/data/game_match.dart';
import '../../domains/matches/state/turn_form_state.dart';
import 'proto_widgets.dart';

const _counterLabels = {
  TurnCounter.doubleBlade: '雙刃',
  TurnCounter.darkBlade: '暗刃',
  TurnCounter.giantBlade: '巨刃',
  TurnCounter.faithful: '信者',
};

/// 記錄回合（白薔薇）：第幾回合、誰主導、點選出牌的座位、四種數量、有沒有白薔薇。
class TurnFormSection extends ConsumerStatefulWidget {
  const TurnFormSection({
    required this.matchId,
    required this.match,
    super.key,
  });

  final String matchId;
  final GameMatch match;

  @override
  ConsumerState<TurnFormSection> createState() => _TurnFormSectionState();
}

class _TurnFormSectionState extends ConsumerState<TurnFormSection> {
  final _turnNumber = TextEditingController(text: '1');

  @override
  void dispose() {
    _turnNumber.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = turnFormProvider(widget.matchId);
    // 送出成功後表單會自動前進到下一個回合，輸入欄位跟著更新
    ref.listen(provider.select((s) => s.turnNumber), (_, next) {
      if (_turnNumber.text != '$next') _turnNumber.text = '$next';
    });
    final form = ref.watch(provider);
    final notifier = ref.read(provider.notifier);
    final seats = widget.match.participants;

    return Column(
      key: const Key('turn-form'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(top: 8, bottom: 12),
          child: Text('記錄回合'),
        ),
        TextField(
          key: const Key('turn-number'),
          controller: _turnNumber,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: '第幾回合',
            errorText: form.errors['turnNumber'],
          ),
          onChanged: (v) => notifier.setTurnNumber(int.tryParse(v.trim()) ?? 0),
        ),
        DropdownButtonFormField<int>(
          key: const Key('turn-leader'),
          initialValue: seats.any((p) => p.seatNumber == form.leaderSeat)
              ? form.leaderSeat
              : null,
          decoration: InputDecoration(
            labelText: '主導的座位',
            errorText: form.errors['leaderSeat'],
          ),
          items: [
            for (final p in seats)
              DropdownMenuItem(
                value: p.seatNumber,
                child: Text('${p.seatNumber} ${p.displayName}'),
              ),
          ],
          onChanged: notifier.setLeaderSeat,
        ),
        const Text('出牌的座位（點選）'),
        Wrap(
          spacing: 8,
          children: [
            for (final p in seats)
              FilterChip(
                key: Key('turn-seat-${p.seatNumber}'),
                label: Text('${p.seatNumber} ${p.displayName}'),
                selected: form.playedSeats.contains(p.seatNumber),
                onSelected: (_) => notifier.togglePlayedSeat(p.seatNumber),
              ),
          ],
        ),
        if (form.errors['playedSeats'] != null)
          FieldErrorText(form.errors['playedSeats']),
        for (final counter in TurnCounter.values)
          Row(
            children: [
              SizedBox(width: 56, child: Text(_counterLabels[counter]!)),
              IconButton(
                key: Key('turn-${counter.name}-dec'),
                icon: const Icon(Icons.remove),
                onPressed: () =>
                    notifier.setCount(counter, form.count(counter) - 1),
              ),
              Text(
                '${form.count(counter)}',
                key: Key('turn-${counter.name}-count'),
              ),
              IconButton(
                key: Key('turn-${counter.name}-inc'),
                icon: const Icon(Icons.add),
                onPressed: () =>
                    notifier.setCount(counter, form.count(counter) + 1),
              ),
            ],
          ),
        SwitchListTile(
          key: const Key('turn-white-rose'),
          title: const Text('有白薔薇'),
          value: form.hasWhiteRose,
          onChanged: notifier.setHasWhiteRose,
        ),
        if (form.error != null) ErrorLine(form.error!),
        if (form.message != null) SuccessLine(form.message!),
        if (form.overwrite != null)
          OverwritePromptCard(
            text: overwritePromptText,
            existing: _describe(form.overwrite!.existing),
            busy: form.busy,
            onConfirm: notifier.confirmOverwrite,
            onCancel: notifier.cancelOverwrite,
          ),
        FilledButton(
          key: const Key('turn-submit'),
          onPressed: form.busy ? null : notifier.submit,
          child: Text(form.busy ? '送出中…' : '記錄這個回合'),
        ),
      ],
    );
  }

  String _describe(Map<String, dynamic> existing) =>
      '第 ${existing['turn_number']} 回合，主導座位 ${existing['seat_number']}，'
      '${jsonEncode(existing['game_data'])}';
}
