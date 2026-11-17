import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/dev/widgets/dev_user_switcher.dart';
import 'theme/app_spacing.dart';

/// 畫面框架：開發環境在最上方掛身分切換器（正式環境切換器自己不顯示）。
class AppShell extends StatelessWidget {
  const AppShell({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Material(
      child: Column(
        children: [
          const DevUserSwitcher(),
          const _TemporaryNav(),
          Expanded(child: child),
        ],
      ),
    );
  }
}

/// 暫時的頁面入口。底部導覽列完成後由它取代，到時刪除這個元件。
class _TemporaryNav extends StatelessWidget {
  const _TemporaryNav();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.small),
      child: Row(
        children: [
          TextButton.icon(
            key: const Key('shell-nav-home'),
            onPressed: () => context.go('/'),
            icon: const Icon(Icons.home_outlined),
            label: const Text('首頁'),
          ),
          TextButton.icon(
            key: const Key('shell-nav-groups'),
            onPressed: () => context.go('/groups'),
            icon: const Icon(Icons.groups_outlined),
            label: const Text('揪團'),
          ),
          TextButton.icon(
            key: const Key('shell-nav-advisor'),
            onPressed: () => context.go('/games-advisor'),
            icon: const Icon(Icons.casino_outlined),
            label: const Text('推薦'),
          ),
          TextButton.icon(
            key: const Key('shell-nav-rules'),
            onPressed: () => context.go('/rules'),
            icon: const Icon(Icons.menu_book_outlined),
            label: const Text('規則'),
          ),
          TextButton.icon(
            key: const Key('shell-nav-booking'),
            onPressed: () => context.go('/booking'),
            icon: const Icon(Icons.event_seat_outlined),
            label: const Text('訂位'),
          ),
        ],
      ),
    );
  }
}
