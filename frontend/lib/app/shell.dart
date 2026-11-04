import 'package:flutter/material.dart';

import '../core/dev/widgets/dev_user_switcher.dart';

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
          Expanded(child: child),
        ],
      ),
    );
  }
}
