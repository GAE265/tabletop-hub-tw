import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/dev/state/dev_user_state.dart';
import 'notifications/notification_bell.dart';
import 'theme/app_colors.dart';
import 'theme/app_spacing.dart';

/// 主要導覽列的一個項目。[keyName] 掛在項目的 [Semantics] 上（測試與無障礙都用它判斷選取狀態）。
class NavItem {
  const NavItem({
    required this.path,
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.keyName,
  });

  final String path;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final String keyName;
}

/// 依序為首頁、揪團、推薦、規則、訂位、戰績。
const navItems = [
  NavItem(
    path: '/',
    label: '首頁',
    icon: Icons.home_outlined,
    selectedIcon: Icons.home,
    keyName: 'shell-nav-home',
  ),
  NavItem(
    path: '/groups',
    label: '揪團',
    icon: Icons.groups_outlined,
    selectedIcon: Icons.groups,
    keyName: 'shell-nav-groups',
  ),
  NavItem(
    path: '/games-advisor',
    label: '推薦',
    icon: Icons.casino_outlined,
    selectedIcon: Icons.casino,
    keyName: 'shell-nav-advisor',
  ),
  NavItem(
    path: '/rules',
    label: '規則',
    icon: Icons.menu_book_outlined,
    selectedIcon: Icons.menu_book,
    keyName: 'shell-nav-rules',
  ),
  NavItem(
    path: '/booking',
    label: '訂位',
    icon: Icons.event_seat_outlined,
    selectedIcon: Icons.event_seat,
    keyName: 'shell-nav-booking',
  ),
  NavItem(
    path: '/matches',
    label: '戰績',
    icon: Icons.emoji_events_outlined,
    selectedIcon: Icons.emoji_events,
    keyName: 'shell-nav-matches',
  ),
];

/// 只有管理員看得到的項目，接在 [navItems] 後面（add-rules-ingest-page）。
const adminNavItems = [
  NavItem(
    path: '/rules-ingest',
    label: '匯入',
    icon: Icons.upload_file_outlined,
    selectedIcon: Icons.upload_file,
    keyName: 'shell-nav-rules-ingest',
  ),
];

/// 店家人員與管理員才看得到的項目，插在「規則」後面（add-rules-video-mobile）。
const staffNavItems = [
  NavItem(
    path: '/videos',
    label: '影片',
    icon: Icons.video_library_outlined,
    selectedIcon: Icons.video_library,
    keyName: 'shell-nav-videos',
  ),
];

/// 依角色決定要顯示的導覽項目：店家人員與管理員多了 [staffNavItems]（放在「規則」後面），
/// 管理員再多 [adminNavItems]。
List<NavItem> visibleNavItems(String? role) {
  final staff = role == 'shop_staff' || role == 'admin';
  return [
    for (final item in navItems) ...[
      item,
      if (staff && item.path == '/rules') ...staffNavItems,
    ],
    if (role == 'admin') ...adminNavItems,
  ];
}

/// 目前身分要顯示的導覽項目。
final visibleNavItemsProvider = Provider<List<NavItem>>(
  (ref) => visibleNavItems(ref.watch(currentDevUserProvider)?.role),
);

/// 目前路徑對應的導覽項目路徑；不屬於任何項目（例如 `/health`、`/proto/...`）時為 null。
///
/// 首頁只在路徑剛好是 `/` 時選取；其他項目在路徑等於它或是它的子路徑時選取。
String? selectedNavPath(String path) {
  if (path == '/') return '/';
  for (final item in [
    ...navItems.skip(1),
    ...staffNavItems,
    ...adminNavItems,
  ]) {
    if (path == item.path || path.startsWith('${item.path}/')) {
      return item.path;
    }
  }
  return null;
}

/// 手機：畫面底部的導覽列。
class BottomNavigation extends ConsumerWidget {
  const BottomNavigation({required this.location, super.key});

  final String location;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = selectedNavPath(location);
    final items = ref.watch(visibleNavItemsProvider);
    return Material(
      color: AppColors.surface,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppColors.border)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: AppSizes.navigationBarHeight,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.small),
              child: Row(
                children: [
                  for (final item in items)
                    Expanded(
                      child: _NavButton(
                        item: item,
                        selected: item.path == selected,
                        vertical: true,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 平板與桌機：畫面頂部的導覽列，含品牌與登入按鈕。
class TopNavigation extends ConsumerWidget {
  const TopNavigation({required this.location, super.key});

  final String location;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = selectedNavPath(location);
    final items = ref.watch(visibleNavItemsProvider);
    return Material(
      color: AppColors.surface,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.border)),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.splitContentMaxWidth,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.large,
                vertical: AppSpacing.small,
              ),
              child: Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: AppSpacing.medium,
                runSpacing: AppSpacing.small,
                children: [
                  const BrandMark(),
                  Wrap(
                    spacing: AppSpacing.xSmall,
                    children: [
                      for (final item in items)
                        _NavButton(
                          item: item,
                          selected: item.path == selected,
                          vertical: false,
                        ),
                    ],
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      NotificationBell(key: Key('shell-notification-bell')),
                      SizedBox(width: AppSpacing.small),
                      LoginButton(key: Key('shell-login')),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 手機：畫面頂部只放通知鈴鐺的窄列（底部導覽已經有六個項目）。
class MobileTopBar extends StatelessWidget {
  const MobileTopBar({super.key});

  @override
  Widget build(BuildContext context) {
    return const Material(
      color: AppColors.surface,
      child: SafeArea(
        bottom: false,
        child: Align(
          alignment: Alignment.centerRight,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: AppSpacing.small),
            child: NotificationBell(key: Key('shell-notification-bell')),
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.item,
    required this.selected,
    required this.vertical,
  });

  final NavItem item;
  final bool selected;
  final bool vertical;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.primaryText : AppColors.inkMuted;
    final textTheme = Theme.of(context).textTheme;
    final label = Text(
      item.label,
      // 手機底部項目變多（管理員有七項）時不換行
      maxLines: 1,
      softWrap: false,
      style: (vertical ? textTheme.labelMedium : textTheme.labelLarge)!
          .copyWith(
            color: color,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
          ),
    );
    final icon = Icon(selected ? item.selectedIcon : item.icon, color: color);
    return Semantics(
      key: Key(item.keyName),
      selected: selected,
      button: true,
      child: Material(
        color: selected ? AppColors.primaryTint : Colors.transparent,
        borderRadius: BorderRadius.circular(AppRadius.button),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => context.go(item.path),
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              minHeight: AppSizes.minTouchTarget,
            ),
            child: Padding(
              padding: EdgeInsets.symmetric(
                // 手機底部每項較窄，左右留白縮小，文字才放得下
                horizontal: vertical ? AppSpacing.xSmall : AppSpacing.medium,
                vertical: AppSpacing.xSmall,
              ),
              child: vertical
                  ? Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [icon, label],
                    )
                  : Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        icon,
                        const SizedBox(width: AppSpacing.small),
                        label,
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 品牌標誌與名稱「遊任有娛」。
class BrandMark extends StatelessWidget {
  const BrandMark({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: AppSizes.brandMark,
          height: AppSizes.brandMark,
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(AppRadius.button),
          ),
          child: Icon(
            Icons.casino_outlined,
            color: theme.colorScheme.onPrimary,
          ),
        ),
        const SizedBox(width: AppSpacing.small),
        Text(
          '遊任有娛',
          style: theme.textTheme.titleLarge!.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

/// 登入按鈕。`auth` 尚未完成，按下只提示「登入功能即將推出」。
/// [compact] 時只有圖示（手機首頁頂部）。
class LoginButton extends StatelessWidget {
  const LoginButton({this.compact = false, super.key});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    void onPressed() => ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('登入功能即將推出')));
    if (compact) {
      return IconButton.outlined(
        tooltip: '登入',
        onPressed: onPressed,
        icon: const Icon(Icons.person_outline),
      );
    }
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: const Icon(Icons.person_outline),
      label: const Text('登入'),
    );
  }
}
