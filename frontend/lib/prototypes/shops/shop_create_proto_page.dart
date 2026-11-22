import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/dev/state/dev_user_state.dart';
import '../../domains/shops/state/shops_state.dart';

/// 新增店家參考畫面（`/proto/shops/new`）。成功後前往新店的庫存參考畫面。
///
/// 只有店家人員與管理員可以使用；其他人只看到提示。
class ShopCreateProtoPage extends ConsumerStatefulWidget {
  const ShopCreateProtoPage({super.key});

  @override
  ConsumerState<ShopCreateProtoPage> createState() =>
      _ShopCreateProtoPageState();
}

class _ShopCreateProtoPageState extends ConsumerState<ShopCreateProtoPage> {
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _address.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(shopsProvider.select((s) => s.createdShop), (previous, shop) {
      if (shop != null && shop.id != previous?.id) {
        context.go('/proto/shops/${shop.id}/games');
      }
    });
    final role = ref.watch(currentDevUserProvider)?.role;
    final allowed = role == 'shop_staff' || role == 'admin';
    final state = ref.watch(shopsProvider);
    return Scaffold(
      key: const Key('shop-create-page'),
      appBar: AppBar(title: const Text('新增店家（參考畫面）')),
      body: !allowed
          ? const Center(
              child: Text(
                '只有店家人員與管理員可以新增店家',
                key: Key('shop-create-forbidden'),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                TextField(
                  key: const Key('shop-name-field'),
                  controller: _name,
                  decoration: const InputDecoration(labelText: '店名（必填）'),
                ),
                TextField(
                  key: const Key('shop-phone-field'),
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: '電話'),
                ),
                TextField(
                  key: const Key('shop-address-field'),
                  controller: _address,
                  decoration: const InputDecoration(labelText: '地址'),
                ),
                FilledButton(
                  key: const Key('shop-create-button'),
                  onPressed: state.loading
                      ? null
                      : () => ref
                            .read(shopsProvider.notifier)
                            .createShop(
                              name: _name.text,
                              phone: _phone.text,
                              address: _address.text,
                            ),
                  child: Text(state.loading ? '建立中…' : '建立店家'),
                ),
                if (state.isError && state.message != null)
                  Text(state.message!, key: const Key('shop-create-error')),
              ],
            ),
    );
  }
}
