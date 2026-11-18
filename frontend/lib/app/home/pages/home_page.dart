import 'package:flutter/material.dart';

import '../../../core/layout/breakpoints.dart';
import '../../navigation.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_spacing.dart';
import 'widgets/home_widgets.dart';

/// 首頁（`/`）：所有角色同一個畫面，把人最快送到下一步。
///
/// 手機版在頁面頂部顯示品牌與登入按鈕；平板與桌機由頂部導覽列顯示。
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      key: const Key('home-page'),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.splitContentMaxWidth,
            ),
            child: ListView(
              padding: EdgeInsets.all(
                mobile ? AppSpacing.medium : AppSpacing.large,
              ),
              children: [
                if (mobile) ...[
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      BrandMark(),
                      LoginButton(key: Key('home-login'), compact: true),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.large),
                ] else
                  const SizedBox(height: AppSpacing.large),
                Text(
                  '今天想怎麼玩？',
                  style:
                      (mobile
                              ? textTheme.headlineMedium
                              : textTheme.displaySmall)!
                          .copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: AppSpacing.small),
                Text(
                  '找遊戲、揪人、訂位、學規則，一個地方搞定。',
                  style: (mobile ? textTheme.bodyLarge : textTheme.titleMedium)!
                      .copyWith(color: AppColors.inkMuted),
                ),
                const SizedBox(height: AppSpacing.large),
                const EntryCards(),
                SizedBox(height: mobile ? AppSpacing.large : AppSpacing.xLarge),
                const UpcomingSection(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
