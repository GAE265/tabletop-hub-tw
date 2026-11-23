import 'package:flutter/material.dart';

import '../core/dev/widgets/dev_user_switcher.dart';
import '../core/layout/breakpoints.dart';
import 'navigation.dart';
import 'theme/wood_background.dart';

/// 畫面框架：開發環境在最上方掛身分切換器（正式環境切換器自己不顯示），
/// 主要導覽列在手機時放在底部，平板與桌機時放在頂部。
/// 通知鈴鐺在平板與桌機放在頂部導覽列，手機放在頂部列。
/// 手機版整個框架放在木紋上：頂部列與浮起來的底部導覽列都看得到木紋（Stitch 設計）。
class AppShell extends StatelessWidget {
  const AppShell({required this.location, required this.child, super.key});

  /// 目前路徑，用來決定導覽列哪個項目是選取狀態。
  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (context.screenSize != ScreenSize.mobile) {
      return Material(
        child: Column(
          children: [
            const DevUserSwitcher(),
            TopNavigation(location: location),
            Expanded(child: child),
          ],
        ),
      );
    }
    return WoodBackground(
      child: Material(
        type: MaterialType.transparency,
        child: Column(
          children: [
            const DevUserSwitcher(),
            const MobileTopBar(),
            if (_floatsNavigation(location))
              Expanded(
                child: _FloatingNavigation(location: location, page: child),
              )
            else ...[
              Expanded(child: child),
              BottomNavigation(location: location),
            ],
          ],
        ),
      ),
    );
  }
}

/// 哪些頁面的內容延伸到浮動導覽列後面（Stitch 設計）。
///
/// 目前是首頁、揪團月曆、桌遊推薦、規則清單、規則教學頁、通知頁、訂位、我的訂位、店家看板、戰績與一局詳情：背景透明（直接看到木紋），內容捲到導覽列後面才不會在導覽列上緣被切成一條線，
/// 頁面也已經在捲動內容最下面留出導覽列的高度。
/// 其他頁面還是米白背景，底部的按鈕也還沒留出導覽列的空間，所以維持內容停在導覽列上方。
bool _floatsNavigation(String location) =>
    location == '/' ||
    location == '/groups' ||
    location == '/games-advisor' ||
    location == '/rules' ||
    location.startsWith('/rules/') ||
    location == '/notifications' ||
    location == '/booking' ||
    location == '/booking/mine' ||
    location == '/booking/board' ||
    location == '/matches' ||
    location.startsWith('/matches/');

/// 導覽列浮在頁面上面；用 MediaQuery 的底部 padding 告訴頁面被蓋住多高，
/// 頁面自己在捲動內容的最下面留出這段空間。
class _FloatingNavigation extends StatelessWidget {
  const _FloatingNavigation({required this.location, required this.page});

  final String location;
  final Widget page;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    final covered = BottomNavigation.extent + media.padding.bottom;
    return Stack(
      children: [
        Positioned.fill(
          child: MediaQuery(
            data: media.copyWith(
              padding: media.padding.copyWith(bottom: covered),
            ),
            child: page,
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: BottomNavigation(location: location),
        ),
      ],
    );
  }
}
