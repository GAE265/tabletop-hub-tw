import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../data/game_match.dart';
import '../../state/result_form_state.dart';
import '../../state/white_rose.dart';
import 'match_widgets.dart';

/// 記錄結果（白薔薇）：獲勝陣營與每個座位的陣營。記錄的人自動確認。
class ResultFormCard extends ConsumerWidget {
  const ResultFormCard({required this.matchId, required this.match, super.key});

  final String matchId;
  final GameMatch match;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = resultFormProvider(matchId);
    final form = ref.watch(provider);
    final n = ref.read(provider.notifier);
    final factions = [
      for (final f in whiteRoseFactions)
        DropdownMenuItem(value: f.code, child: Text(f.label)),
    ];
    return Column(
      key: const Key('result-form'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DropdownButtonFormField<String>(
          key: const Key('result-winning'),
          initialValue: form.winningFaction,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: '獲勝陣營',
            prefixIcon: const Icon(Icons.emoji_events_outlined),
            errorText: form.errors['winningFaction'],
          ),
          items: factions,
          onChanged: n.setWinningFaction,
        ),
        const SizedBox(height: AppSpacing.medium),
        for (final p in match.participants) ...[
          DropdownButtonFormField<String>(
            key: Key('result-faction-${p.seatNumber}'),
            initialValue: form.factions[p.seatNumber],
            isExpanded: true,
            decoration: InputDecoration(
              labelText: '座位 ${p.seatNumber}・${p.displayName} 的陣營',
            ),
            items: factions,
            onChanged: (v) {
              if (v != null) n.setFaction(p.seatNumber, v);
            },
          ),
          const SizedBox(height: AppSpacing.small),
        ],
        FieldError(form.errors['factions']),
        if (form.overwrite case final prompt?) ...[
          const SizedBox(height: AppSpacing.small),
          OverwritePrompt(
            keyPrefix: 'result-overwrite',
            text: '$overwritePromptText更新會清除其他人的確認。',
            existing: _describe(prompt.existing),
            busy: form.busy,
            onConfirm: n.confirmOverwrite,
            onCancel: n.cancelOverwrite,
          ),
        ],
        if (form.message case final message?) ...[
          const SizedBox(height: AppSpacing.small),
          MatchBanner(key: const Key('result-message'), text: message),
        ],
        if (form.error case final error?) ...[
          const SizedBox(height: AppSpacing.small),
          MatchBanner(
            key: const Key('result-error'),
            text: matchErrorText(error),
            isError: true,
          ),
        ],
        const SizedBox(height: AppSpacing.small),
        Align(
          alignment: Alignment.centerLeft,
          child: ThickButton(
            buttonKey: const Key('result-submit'),
            style: ThickStyle.light,
            icon: Icons.flag_outlined,
            label: '記錄勝負結果',
            shadow: AppShadows.soft,
            onPressed: form.busy ? null : n.submit,
          ),
        ),
      ],
    );
  }

  String _describe(Map<String, dynamic> existing) {
    final winning = (existing['result'] as Map?)?['winning_faction'];
    return winning is String ? '${factionLabel(winning)}獲勝' : '已有結果';
  }
}
