import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/dev/state/dev_user_state.dart';
import '../state/shops_state.dart';

/// 導覽列「店家」的入口（`/shops`）：依身分轉到庫存頁或新增店家頁，自己不顯示內容。
class ShopsEntryPage extends ConsumerStatefulWidget {
  const ShopsEntryPage({super.key});

  @override
  ConsumerState<ShopsEntryPage> createState() => _ShopsEntryPageState();
}

class _ShopsEntryPageState extends ConsumerState<ShopsEntryPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final path = resolveShopsEntryPath(
        ref.read(currentDevUserProvider),
        ref.read(shopsProvider).createdShop?.id,
      );
      context.go(path);
    });
  }

  @override
  Widget build(BuildContext context) => const Scaffold(
    key: Key('shops-entry-page'),
    body: Center(child: CircularProgressIndicator()),
  );
}
