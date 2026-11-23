import 'package:flutter/material.dart';

import '../../../core/layout/breakpoints.dart';
import '../../theme/app_spacing.dart';
import '../../theme/wood_background.dart';
import 'widgets/home_widgets.dart';

/// 首頁（`/`）：所有角色同一個畫面，把人最快送到下一步。
///
/// 版面依 Stitch 設計（docs/ui/stitch/）：木紋背景，文字一律放在卡片或白底條上。
/// 品牌與登入由畫面框架顯示（手機頂部列、平板與桌機頂部導覽列）。
/// 手機的畫面框架已經畫了木紋，首頁就不再畫一次，免得兩層木紋接不起來。
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final gap = mobile ? AppSpacing.medium : AppSpacing.large;
    // 底部不用 SafeArea：手機的浮動導覽列蓋住的高度放進捲動內容的留白，
    // 內容才能從導覽列後面捲過去，捲到最底時最後的按鈕停在導覽列上方
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final content = SafeArea(
      bottom: false,
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.splitContentMaxWidth,
          ),
          // 內容不多，一次全部建立（ListView 只建畫面上看得到的部分）
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(gap, gap, gap, gap + bottomInset),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const HomeHero(),
                SizedBox(height: gap),
                const SectionBar(
                  key: Key('home-section-entries'),
                  title: '快速入口',
                ),
                const SizedBox(height: AppSpacing.small),
                const EntryCards(),
                SizedBox(height: gap),
                const UpcomingSection(),
                SizedBox(height: gap),
                const HomeActions(),
                const SizedBox(height: AppSpacing.small),
              ],
            ),
          ),
        ),
      ),
    );
    return Scaffold(
      key: const Key('home-page'),
      backgroundColor: Colors.transparent,
      body: WoodBackground.isPaintedAbove(context)
          ? content
          : WoodBackground(child: content),
    );
  }
}
