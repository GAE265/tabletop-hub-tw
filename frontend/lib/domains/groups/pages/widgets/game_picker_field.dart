import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/api/api_exception.dart';
import '../../data/group.dart';
import '../../state/group_pickers_state.dart';

/// 遊戲的搜尋與複選：輸入關鍵字 → 下方列出結果 → 點選加入；已選的遊戲以標籤顯示，可以移除。
class GamePickerField extends ConsumerStatefulWidget {
  const GamePickerField({
    required this.selected,
    required this.onChanged,
    super.key,
  });

  /// 目前選好的遊戲，依選擇的順序。
  final List<GameRef> selected;
  final ValueChanged<List<GameRef>> onChanged;

  @override
  ConsumerState<GamePickerField> createState() => _GamePickerFieldState();
}

class _GamePickerFieldState extends ConsumerState<GamePickerField> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  GameSearchNotifier get _search => ref.read(gameSearchProvider.notifier);

  void _add(GameRef game) {
    widget.onChanged([...widget.selected, game]);
    _input.clear();
    _search.clear();
  }

  void _remove(GameRef game) {
    widget.onChanged([
      for (final g in widget.selected)
        if (g.id != game.id) g,
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(gameSearchProvider);
    final selectedIds = {for (final g in widget.selected) g.id};
    final text = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          key: const Key('game-search-input'),
          controller: _input,
          onChanged: _search.search,
          decoration: const InputDecoration(
            labelText: '遊戲（選填，可以選多款）',
            hintText: '輸入遊戲名稱搜尋',
            prefixIcon: Icon(Icons.search),
          ),
        ),
        if (state.query.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xSmall),
            child: Card(
              margin: EdgeInsets.zero,
              child: state.results.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(AppSpacing.medium),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (error, _) => ListTile(
                  title: Text(
                    error is ApiException ? error.message : '搜尋失敗，請再試一次',
                  ),
                ),
                data: (games) {
                  final options = [
                    for (final game in games)
                      if (!selectedIds.contains(game.id)) game,
                  ];
                  if (options.isEmpty) {
                    return const ListTile(title: Text('找不到符合的遊戲'));
                  }
                  return Column(
                    children: [
                      for (final game in options)
                        ListTile(
                          key: Key('game-option-${game.id}'),
                          leading: const Icon(Icons.add),
                          title: Text(game.name),
                          onTap: () => _add(game),
                        ),
                    ],
                  );
                },
              ),
            ),
          ),
        if (widget.selected.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.small),
          Wrap(
            spacing: AppSpacing.small,
            runSpacing: AppSpacing.xSmall,
            children: [
              for (final game in widget.selected)
                InputChip(
                  key: Key('game-chip-${game.id}'),
                  label: Text(game.name, style: text.labelLarge),
                  deleteIcon: const Icon(Icons.close),
                  deleteButtonTooltipMessage: '移除${game.name}',
                  onDeleted: () => _remove(game),
                ),
            ],
          ),
        ],
      ],
    );
  }
}
