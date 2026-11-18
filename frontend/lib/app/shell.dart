import 'package:flutter/material.dart';

import '../core/dev/widgets/dev_user_switcher.dart';
import '../core/layout/breakpoints.dart';
import 'navigation.dart';

/// 畫面框架：開發環境在最上方掛身分切換器（正式環境切換器自己不顯示），
/// 主要導覽列在手機時放在底部，平板與桌機時放在頂部。
class AppShell extends StatelessWidget {
  const AppShell({required this.location, required this.child, super.key});

  /// 目前路徑，用來決定導覽列哪個項目是選取狀態。
  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    return Material(
      child: Column(
        children: [
          const DevUserSwitcher(),
          if (!mobile) TopNavigation(location: location),
          Expanded(child: child),
          if (mobile) BottomNavigation(location: location),
        ],
      ),
    );
  }
}
