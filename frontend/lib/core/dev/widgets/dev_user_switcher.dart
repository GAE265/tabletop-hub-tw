import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/app_config.dart';
import '../state/dev_user_state.dart';

/// 開發用身分切換器。只在開發環境出現；正式環境不顯示、也不呼叫 API。
class DevUserSwitcher extends ConsumerWidget {
  const DevUserSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(appConfigProvider).devUserEnabled) {
      return const SizedBox.shrink();
    }

    final users = ref.watch(devUsersProvider);
    return users.when(
      loading: () => const ListTile(dense: true, title: Text('載入測試帳號…')),
      error: (_, _) => ListTile(
        dense: true,
        title: const Text('無法載入測試帳號'),
        trailing: TextButton(
          onPressed: () => ref.invalidate(devUsersProvider),
          child: const Text('重試'),
        ),
      ),
      data: (list) {
        if (list.isEmpty) {
          return const ListTile(dense: true, title: Text('尚無測試帳號，請先執行 seed'));
        }
        final current = ref.watch(currentDevUserProvider);
        return ListTile(
          dense: true,
          title: const Text('開發身分'),
          trailing: DropdownButton<String>(
            value: current?.id,
            items: [
              for (final user in list)
                DropdownMenuItem(
                  value: user.id,
                  child: Text('${user.displayName}（${user.role}）'),
                ),
            ],
            onChanged: (id) =>
                ref.read(selectedDevUserIdProvider.notifier).select(id),
          ),
        );
      },
    );
  }
}
