import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/shops/state/shops_state.dart';

/// 店家庫存參考畫面（`/proto/shops/:shopId/games`）：看目前有哪些桌遊、加入、移除。
class ShopInventoryProtoPage extends ConsumerStatefulWidget {
  const ShopInventoryProtoPage({required this.shopId, super.key});

  final String shopId;

  @override
  ConsumerState<ShopInventoryProtoPage> createState() =>
      _ShopInventoryProtoPageState();
}

class _ShopInventoryProtoPageState
    extends ConsumerState<ShopInventoryProtoPage> {
  int? _selectedGameId;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    final notifier = ref.read(shopsProvider.notifier);
    await notifier.loadInventory(widget.shopId);
    await notifier.loadChoices();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(shopsProvider);
    final inStock = {for (final g in state.inventory) g.gameId};
    final addable = [
      for (final c in state.choices)
        if (!inStock.contains(c.id)) c,
    ];
    // 剛加入的那款已不在可加入清單，選取值要跟著清掉
    final selected = addable.any((c) => c.id == _selectedGameId)
        ? _selectedGameId
        : null;
    return Scaffold(
      key: const Key('shop-inventory-page'),
      appBar: AppBar(title: const Text('桌遊庫存（參考畫面）')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  key: const Key('shop-game-picker'),
                  initialValue: selected,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: '選一款桌遊'),
                  items: [
                    for (final c in addable)
                      DropdownMenuItem(value: c.id, child: Text(c.name)),
                  ],
                  onChanged: (id) => setState(() => _selectedGameId = id),
                ),
              ),
              FilledButton(
                key: const Key('shop-game-add-button'),
                onPressed: state.loading || selected == null
                    ? null
                    : () => ref
                          .read(shopsProvider.notifier)
                          .addGame(widget.shopId, selected),
                child: const Text('加入'),
              ),
            ],
          ),
          if (state.isError && state.message != null)
            Row(
              children: [
                Expanded(
                  child: Text(
                    state.message!,
                    key: const Key('shop-inventory-error'),
                  ),
                ),
                TextButton(
                  key: const Key('shop-inventory-retry'),
                  onPressed: _load,
                  child: const Text('重試'),
                ),
              ],
            ),
          if (state.loading && !state.inventoryLoaded)
            const Center(
              child: CircularProgressIndicator(
                key: Key('shop-inventory-loading'),
              ),
            )
          else if (state.inventoryLoaded && state.inventory.isEmpty)
            const Text('這間店還沒有桌遊，從上面挑一款加入吧', key: Key('shop-inventory-empty'))
          else
            for (final game in state.inventory)
              ListTile(
                key: Key('shop-game-${game.gameId}'),
                title: Text(game.name),
                trailing: IconButton(
                  key: Key('shop-game-remove-${game.gameId}'),
                  tooltip: '移除',
                  icon: const Icon(Icons.delete_outline),
                  onPressed: state.loading
                      ? null
                      : () => ref
                            .read(shopsProvider.notifier)
                            .removeGame(widget.shopId, game.gameId),
                ),
              ),
        ],
      ),
    );
  }
}
