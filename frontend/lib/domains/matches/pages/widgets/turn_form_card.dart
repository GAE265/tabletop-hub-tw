import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../data/game_match.dart';
import '../../state/turn_form_state.dart';
import 'match_widgets.dart';

const _counterLabels = {
  TurnCounter.doubleBlade: '雙刃',
  TurnCounter.darkBlade: '暗刃',
  TurnCounter.giantBlade: '巨刃',
  TurnCounter.faithful: '信者',
};

/// 記錄回合（白薔薇）：第幾回合、首家（有金幣，選填）、出牌的座位（可以都不選）、四種數量、
/// 有沒有白薔薇、有沒有司教。
class TurnFormCard extends ConsumerStatefulWidget {
  const TurnFormCard({required this.matchId, required this.match, super.key});

  final String matchId;
  final GameMatch match;

  @override
  ConsumerState<TurnFormCard> createState() => _TurnFormCardState();
}

class _TurnFormCardState extends ConsumerState<TurnFormCard> {
  late final _turnNumber = TextEditingController(
    text: '${ref.read(turnFormProvider(widget.matchId)).turnNumber}',
  );

  @override
  void dispose() {
    _turnNumber.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = turnFormProvider(widget.matchId);
    // 記錄成功後 state 會前進到下一回合，輸入欄位跟著更新
    ref.listen(provider.select((s) => s.turnNumber), (_, next) {
      if (_turnNumber.text != '$next') _turnNumber.text = '$next';
    });
    final form = ref.watch(provider);
    final n = ref.read(provider.notifier);
    final theme = Theme.of(context);
    final people = widget.match.participants;
    return Column(
      key: const Key('turn-form'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '記錄回合',
          style: theme.textTheme.titleSmall!.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: AppSpacing.small),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: AppSizes.turnNumberFieldWidth,
              child: TextField(
                key: const Key('turn-number'),
                controller: _turnNumber,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: '第幾回合',
                  errorText: form.errors['turnNumber'],
                ),
                onChanged: (v) => n.setTurnNumber(int.tryParse(v.trim()) ?? 0),
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            Expanded(
              // 記錄成功後首家（有金幣）會清空；換 Key 讓下拉選單跟著重建
              child: KeyedSubtree(
                key: const Key('turn-first-seat'),
                child: DropdownButtonFormField<int>(
                  key: ValueKey(('first', form.turnNumber, form.firstSeat)),
                  initialValue: form.firstSeat,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: '首家（有金幣，選填）'),
                  items: [
                    const DropdownMenuItem<int>(
                      value: null,
                      child: Text('不指定'),
                    ),
                    for (final p in people)
                      DropdownMenuItem(
                        value: p.seatNumber,
                        child: Text('座位 ${p.seatNumber}・${p.displayName}'),
                      ),
                  ],
                  onChanged: n.setFirstSeat,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.medium),
        Text('出牌的座位（點選）', style: theme.textTheme.bodyMedium),
        const SizedBox(height: AppSpacing.xSmall),
        Wrap(
          spacing: AppSpacing.small,
          runSpacing: AppSpacing.small,
          children: [
            for (final p in people)
              FilterChip(
                key: Key('turn-seat-${p.seatNumber}'),
                label: Text('${p.seatNumber} ${p.displayName}'),
                selected: form.playedSeats.contains(p.seatNumber),
                onSelected: (_) => n.togglePlayedSeat(p.seatNumber),
              ),
          ],
        ),
        FieldError(form.errors['playedSeats']),
        const SizedBox(height: AppSpacing.small),
        Wrap(
          spacing: AppSpacing.large,
          children: [
            for (final MapEntry(key: counter, value: label)
                in _counterLabels.entries)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(label),
                  IconButton(
                    key: Key('turn-${counter.name}-dec'),
                    tooltip: '$label 減一',
                    onPressed: form.count(counter) > 0
                        ? () => n.setCount(counter, form.count(counter) - 1)
                        : null,
                    icon: const Icon(Icons.remove),
                  ),
                  Text(
                    '${form.count(counter)}',
                    key: Key('turn-${counter.name}-count'),
                  ),
                  IconButton(
                    key: Key('turn-${counter.name}-inc'),
                    tooltip: '$label 加一',
                    onPressed: () =>
                        n.setCount(counter, form.count(counter) + 1),
                    icon: const Icon(Icons.add),
                  ),
                ],
              ),
          ],
        ),
        _OnceCardSwitch(
          switchKey: const Key('turn-white-rose'),
          label: '有白薔薇',
          value: form.hasWhiteRose,
          recordedTurn: recordedTurnOf(
            OnceCard.whiteRose,
            widget.match.turns,
            editingTurn: form.turnNumber,
          ),
          error: form.errors['hasWhiteRose'],
          onChanged: n.setHasWhiteRose,
        ),
        _OnceCardSwitch(
          switchKey: const Key('turn-cardinal'),
          label: '司教',
          value: form.hasCardinal,
          recordedTurn: recordedTurnOf(
            OnceCard.cardinal,
            widget.match.turns,
            editingTurn: form.turnNumber,
          ),
          error: form.errors['hasCardinal'],
          onChanged: n.setHasCardinal,
        ),
        if (form.overwrite case final prompt?) ...[
          OverwritePrompt(
            keyPrefix: 'turn-overwrite',
            text: overwritePromptText,
            existing: [
              '第 ${prompt.existing['turn_number']} 回合',
              if (prompt.existing['seat_number'] case final seat?)
                '首家（有金幣）座位 $seat',
            ].join('・'),
            busy: form.busy,
            onConfirm: n.confirmOverwrite,
            onCancel: n.cancelOverwrite,
          ),
          const SizedBox(height: AppSpacing.small),
        ],
        if (form.message case final message?) ...[
          MatchBanner(key: const Key('turn-message'), text: message),
          const SizedBox(height: AppSpacing.small),
        ],
        if (form.error case final error?) ...[
          MatchBanner(
            key: const Key('turn-error'),
            text: matchErrorText(error),
            isError: true,
          ),
          const SizedBox(height: AppSpacing.small),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: ThickButton(
            buttonKey: const Key('turn-submit'),
            style: ThickStyle.dark,
            icon: Icons.edit_note,
            label: '記錄這個回合',
            shadow: AppShadows.soft,
            onPressed: form.busy ? null : n.submit,
          ),
        ),
      ],
    );
  }
}

/// 一局只出現一次的牌（白薔薇、司教）的開關。
///
/// 別的回合已經記過（[recordedTurn] 不為 null）時，開關關著就不能打開，下方顯示是哪一回合；
/// 如果已經打開（例如打開後才改了回合編號），仍然可以關掉。
class _OnceCardSwitch extends StatelessWidget {
  const _OnceCardSwitch({
    required this.switchKey,
    required this.label,
    required this.value,
    required this.recordedTurn,
    required this.error,
    required this.onChanged,
  });

  final Key switchKey;
  final String label;
  final bool value;
  final int? recordedTurn;
  final String? error;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final turn = recordedTurn;
    return SwitchListTile(
      key: switchKey,
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      subtitle: error != null
          ? FieldError(error)
          : turn == null
          ? null
          : Text(onceCardReason(turn)),
      value: value,
      onChanged: turn == null || value ? onChanged : null,
    );
  }
}
