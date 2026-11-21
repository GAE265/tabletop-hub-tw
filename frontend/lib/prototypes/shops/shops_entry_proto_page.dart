import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/dev/state/dev_user_state.dart';
import '../../domains/shops/state/shops_state.dart';

/// shops 入口參考畫面（`/proto/shops`）：依身分轉到庫存頁或新增店家頁，自己不顯示內容。
///
/// 要去哪一頁由 `resolveShopsEntryPath` 決定，它回傳的是正式路徑；
/// 參考畫面掛在 `/proto` 底下，所以這裡自己加上前綴。
class ShopsEntryProtoPage extends ConsumerStatefulWidget {
  const ShopsEntryProtoPage({super.key});

  @override
  ConsumerState<ShopsEntryProtoPage> createState() =>
      _ShopsEntryProtoPageState();
}

class _ShopsEntryProtoPageState extends ConsumerState<ShopsEntryProtoPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final path = resolveShopsEntryPath(
        ref.read(currentDevUserProvider),
        ref.read(shopsProvider).createdShop?.id,
      );
      context.go('/proto$path');
    });
  }

  @override
  Widget build(BuildContext context) => const Scaffold(
    key: Key('shops-entry-page'),
    body: Center(child: CircularProgressIndicator()),
  );
}
