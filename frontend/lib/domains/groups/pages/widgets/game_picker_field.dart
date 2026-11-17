import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/api/api_exception.dart';
import '../../data/group.dart';
import '../../state/group_pickers_state.dart';

/// 遊戲的下拉式選單：點欄位展開全部遊戲，勾選複選，上方搜尋框在本機篩選；
/// 選好的遊戲以標籤顯示在欄位下方，可以移除。
class GamePickerField extends ConsumerStatefulWidget {
  const GamePickerField({
    required this.selected,
    required this.onChanged,
    super.key,
  });

  /// 目前選好的遊戲，依勾選的順序。
  final List<GameRef> selected;
  final ValueChanged<List<GameRef>> onChanged;

  @override
  ConsumerState<GamePickerField> createState() => _GamePickerFieldState();
}

class _GamePickerFieldState extends ConsumerState<GamePickerField> {
  final _search = TextEditingController();
  bool _open = false;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _toggleOpen() => setState(() {
    _open = !_open;
    if (!_open) _search.clear();
  });

  void _toggle(GameRef game, bool checked) {
    widget.onChanged(
      checked
          ? [...widget.selected, game]
          : [
              for (final g in widget.selected)
                if (g.id != game.id) g,
            ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedIds = {for (final g in widget.selected) g.id};
    final count = widget.selected.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        InkWell(
          key: const Key('game-picker-field'),
          onTap: _toggleOpen,
          borderRadius: BorderRadius.circular(AppRadius.button),
          child: InputDecorator(
            isFocused: _open,
            decoration: InputDecoration(
              labelText: '遊戲（選填，可以選多款）',
              prefixIcon: const Icon(Icons.casino_outlined),
              suffixIcon: Icon(
                _open ? Icons.arrow_drop_up : Icons.arrow_drop_down,
              ),
            ),
            child: Text(count == 0 ? '點選遊戲' : '已選 $count 款'),
          ),
        ),
        if (_open)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xSmall),
            child: Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.small),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      key: const Key('game-search-input'),
                      controller: _search,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        hintText: '搜尋遊戲名稱',
                        prefixIcon: Icon(Icons.search),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xSmall),
                    _GameOptions(
                      query: _search.text,
                      selectedIds: selectedIds,
                      onToggle: _toggle,
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: _toggleOpen,
                        child: const Text('完成'),
                      ),
                    ),
                  ],
                ),
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
                  label: Text(game.name),
                  deleteIcon: const Icon(Icons.close),
                  deleteButtonTooltipMessage: '移除${game.name}',
                  onDeleted: () => _toggle(game, false),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _GameOptions extends ConsumerWidget {
  const _GameOptions({
    required this.query,
    required this.selectedIds,
    required this.onToggle,
  });

  final String query;
  final Set<int> selectedIds;
  final void Function(GameRef game, bool checked) onToggle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref
        .watch(gameOptionsProvider)
        .when(
          loading: () => const Padding(
            padding: EdgeInsets.all(AppSpacing.medium),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (error, _) => ListTile(
            title: Text(error is ApiException ? error.message : '無法載入遊戲清單'),
            trailing: TextButton(
              onPressed: () => ref.invalidate(gameOptionsProvider),
              child: const Text('重試'),
            ),
          ),
          data: (games) {
            final options = filterGames(games, query);
            if (options.isEmpty) {
              return const ListTile(title: Text('找不到符合的遊戲'));
            }
            return Column(
              children: [
                for (final game in options)
                  CheckboxListTile(
                    key: Key('game-option-${game.id}'),
                    value: selectedIds.contains(game.id),
                    title: Text(game.name),
                    controlAffinity: ListTileControlAffinity.leading,
                    onChanged: (checked) => onToggle(game, checked ?? false),
                  ),
              ],
            );
          },
        );
  }
}
