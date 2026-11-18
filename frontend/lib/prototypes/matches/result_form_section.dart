import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/matches/data/game_match.dart';
import '../../domains/matches/state/result_form_state.dart';
import '../../domains/matches/state/white_rose.dart';
import 'proto_widgets.dart';

/// 記錄結果（陣營勝負）：獲勝陣營，以及每個座位的陣營。
/// 已經有結果時再送出會先問「已經有人記錄了，要更新嗎？」，更新會清除其他人的確認。
class ResultFormSection extends ConsumerWidget {
  const ResultFormSection({
    required this.matchId,
    required this.match,
    super.key,
  });

  final String matchId;
  final GameMatch match;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = resultFormProvider(matchId);
    final form = ref.watch(provider);
    final notifier = ref.read(provider.notifier);

    return Column(
      key: const Key('result-form'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        DropdownButtonFormField<String>(
          key: const Key('result-winning'),
          initialValue: form.winningFaction,
          decoration: InputDecoration(
            labelText: '獲勝陣營',
            errorText: form.errors['winningFaction'],
          ),
          items: [
            for (final f in whiteRoseFactions)
              DropdownMenuItem(value: f.code, child: Text(f.label)),
          ],
          onChanged: notifier.setWinningFaction,
        ),
        const Text('每個座位的陣營'),
        for (final p in match.participants)
          DropdownButtonFormField<String>(
            key: Key('result-faction-${p.seatNumber}'),
            initialValue: form.factions[p.seatNumber],
            decoration: InputDecoration(
              labelText: '${p.seatNumber} ${p.displayName}',
            ),
            items: [
              for (final f in whiteRoseFactions)
                DropdownMenuItem(value: f.code, child: Text(f.label)),
            ],
            onChanged: (v) {
              if (v != null) notifier.setFaction(p.seatNumber, v);
            },
          ),
        if (form.errors['factions'] != null)
          FieldErrorText(form.errors['factions']),
        if (form.error != null) ErrorLine(form.error!),
        if (form.message != null) SuccessLine(form.message!),
        if (form.overwrite != null)
          OverwritePromptCard(
            text: overwritePromptText,
            existing: factionLabel(
              (form.overwrite!.existing['result'] as Map?)?['winning_faction']
                  as String?,
            ),
            busy: form.busy,
            onConfirm: notifier.confirmOverwrite,
            onCancel: notifier.cancelOverwrite,
          ),
        FilledButton(
          key: const Key('result-submit'),
          onPressed: form.busy ? null : notifier.submit,
          child: Text(form.busy ? '送出中…' : '記錄結果'),
        ),
      ],
    );
  }
}
