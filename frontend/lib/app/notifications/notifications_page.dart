import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/booking/pages/widgets/booking_notifications_list.dart';
import '../../domains/booking/state/booking_notifications_state.dart';
import '../../domains/groups/pages/widgets/group_notifications_list.dart';
import '../../domains/groups/state/group_notifications_state.dart';
import '../../core/widgets/pill_badge.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/thick_widgets.dart';
import '../theme/wood_background.dart';

/// 通知頁 `/notifications`：「揪團」「訂位」兩個分頁（add-booking-notifications D4）。
///
/// Stitch 版面：木紋背景，頁首白底條有「通知」、總未讀數與分頁膠囊；每則通知一張厚卡片，依日期分段。
class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 2,
      child: _NotificationsScaffold(),
    );
  }
}

/// 只有訂位有未讀時開「訂位」分頁，其他情況開「揪團」。
int preferredNotificationTab(int? groups, int? bookings) =>
    (groups ?? 0) == 0 && (bookings ?? 0) > 0 ? 1 : 0;

class _NotificationsScaffold extends ConsumerStatefulWidget {
  const _NotificationsScaffold();

  @override
  ConsumerState<_NotificationsScaffold> createState() =>
      _NotificationsScaffoldState();
}

class _NotificationsScaffoldState
    extends ConsumerState<_NotificationsScaffold> {
  /// 使用者自己點過分頁後，就不再自動切換。
  bool _touched = false;

  void _selectPreferred() {
    if (_touched || !mounted) return;
    final index = preferredNotificationTab(
      ref.read(groupUnreadCountProvider),
      ref.read(bookingUnreadCountProvider),
    );
    final controller = DefaultTabController.of(context);
    if (controller.index != index) controller.index = index;
  }

  @override
  void initState() {
    super.initState();
    // 未讀數可能還在查詢；查到之後（見 build 裡的 listen）再決定一次
    WidgetsBinding.instance.addPostFrameCallback((_) => _selectPreferred());
  }

  @override
  Widget build(BuildContext context) {
    final groups = ref.watch(groupUnreadCountProvider);
    final bookings = ref.watch(bookingUnreadCountProvider);
    ref.listen(groupUnreadCountProvider, (_, _) => _selectPreferred());
    ref.listen(bookingUnreadCountProvider, (_, _) => _selectPreferred());
    final total = (groups ?? 0) + (bookings ?? 0);
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium,
            0,
          ),
          child: GlassBar(
            key: const Key('notifications-header'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.notifications_outlined,
                      color: AppColors.primaryText,
                    ),
                    const SizedBox(width: AppSpacing.small),
                    Text(
                      '通知',
                      style: Theme.of(context).textTheme.headlineSmall!
                          .copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(width: AppSpacing.small),
                    if (total > 0)
                      PillBadge(label: '$total 則未讀', tone: PillTone.accent),
                  ],
                ),
                const SizedBox(height: AppSpacing.small),
                Row(
                  children: [
                    _TabPill(
                      key: const Key('notifications-tab-groups'),
                      index: 0,
                      label: '揪團',
                      count: groups,
                      onTap: () => _touched = true,
                    ),
                    const SizedBox(width: AppSpacing.small),
                    _TabPill(
                      key: const Key('notifications-tab-booking'),
                      index: 1,
                      label: '訂位',
                      count: bookings,
                      onTap: () => _touched = true,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const Expanded(
          child: TabBarView(
            children: [GroupNotificationsList(), BookingNotificationsList()],
          ),
        ),
      ],
    );
    return Scaffold(
      key: const Key('notifications-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? body
            : WoodBackground(child: body),
      ),
    );
  }
}

/// 分頁膠囊：選中的是深炭底白字，旁邊是未讀數（沒有未讀時不顯示）。
class _TabPill extends StatelessWidget {
  const _TabPill({
    required this.index,
    required this.label,
    required this.count,
    required this.onTap,
    super.key,
  });

  final int index;
  final String label;
  final int? count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final controller = DefaultTabController.of(context);
    final badge = unreadBadgeLabel(count);
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final selected = controller.index == index;
        final fg = selected ? AppColors.surface : AppColors.ink;
        return Semantics(
          selected: selected,
          button: true,
          child: Material(
            color: selected ? AppColors.ink : AppColors.surface,
            shape: StadiumBorder(
              side: BorderSide(
                color: selected ? AppColors.ink : AppColors.border,
              ),
            ),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () {
                onTap();
                controller.animateTo(index);
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.medium,
                  vertical: AppSpacing.small,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: Theme.of(
                        context,
                      ).textTheme.labelLarge!.copyWith(color: fg),
                    ),
                    if (badge != null) ...[
                      const SizedBox(width: AppSpacing.small),
                      DecoratedBox(
                        decoration: BoxDecoration(
                          color: selected
                              ? AppColors.surface
                              : AppColors.primaryTint,
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: AppSpacing.small,
                          ),
                          child: Text(
                            badge,
                            style: Theme.of(context).textTheme.labelMedium!
                                .copyWith(color: AppColors.primaryText),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
