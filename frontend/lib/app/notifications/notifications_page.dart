import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/booking/pages/widgets/booking_notifications_list.dart';
import '../../domains/booking/state/booking_notifications_state.dart';
import '../../domains/groups/pages/widgets/group_notifications_list.dart';
import '../../domains/groups/state/group_notifications_state.dart';
import '../../domains/matches/pages/widgets/match_notifications_list.dart';
import '../../domains/matches/state/match_notifications_state.dart';
import '../../core/widgets/pill_badge.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/thick_widgets.dart';
import '../theme/wood_background.dart';

/// 通知頁 `/notifications`：「揪團」「訂位」「戰績」三個分頁（add-booking-notifications D4、
/// feature-matches-notifications）。
///
/// Stitch 版面：木紋背景，頁首白底條有「通知」、總未讀數與分頁膠囊；每則通知一張厚卡片，依日期分段。
class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 3,
      child: _NotificationsScaffold(),
    );
  }
}

/// 依「揪團、訂位、戰績」的順序，開第一個有未讀的分頁；都沒有未讀時開「揪團」。
int preferredNotificationTab(int? groups, int? bookings, int? matches) {
  final index = [groups, bookings, matches].indexWhere((c) => (c ?? 0) > 0);
  return index < 0 ? 0 : index;
}

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
      ref.read(matchUnreadCountProvider),
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
    final matches = ref.watch(matchUnreadCountProvider);
    ref.listen(groupUnreadCountProvider, (_, _) => _selectPreferred());
    ref.listen(bookingUnreadCountProvider, (_, _) => _selectPreferred());
    ref.listen(matchUnreadCountProvider, (_, _) => _selectPreferred());
    final total = (groups ?? 0) + (bookings ?? 0) + (matches ?? 0);
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
          child: ThickCard(
            key: const Key('notifications-header'),
            radius: AppRadius.card,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.medium),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Container(
                        width: AppSizes.avatar,
                        height: AppSizes.avatar,
                        decoration: BoxDecoration(
                          color: AppColors.primaryTint,
                          borderRadius: BorderRadius.circular(AppRadius.button),
                        ),
                        child: const Icon(
                          Icons.notifications_outlined,
                          color: AppColors.primaryText,
                        ),
                      ),
                      const SizedBox(
                        width: AppSpacing.small + AppSpacing.xSmall,
                      ),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '通知',
                              style: Theme.of(context).textTheme.headlineSmall!
                                  .copyWith(fontWeight: FontWeight.w700),
                            ),
                            Text(
                              '揪團、訂位與戰績的最新消息',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      if (total > 0)
                        PillBadge(label: '$total 則未讀', tone: PillTone.accent),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.medium),
                  // 分段切換：一條米色軌道，選中的那半是浮起來的白色按鈕
                  DecoratedBox(
                    key: const Key('notifications-tabs'),
                    decoration: BoxDecoration(
                      color: AppColors.neutralTint,
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.xSmall),
                      child: Row(
                        children: [
                          Expanded(
                            child: _Segment(
                              key: const Key('notifications-tab-groups'),
                              index: 0,
                              icon: Icons.groups_outlined,
                              label: '揪團',
                              count: groups,
                              onTap: () => _touched = true,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xSmall),
                          Expanded(
                            child: _Segment(
                              key: const Key('notifications-tab-booking'),
                              index: 1,
                              icon: Icons.event_seat_outlined,
                              label: '訂位',
                              count: bookings,
                              onTap: () => _touched = true,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xSmall),
                          Expanded(
                            child: _Segment(
                              key: const Key('notifications-tab-matches'),
                              index: 2,
                              icon: Icons.emoji_events_outlined,
                              label: '戰績',
                              count: matches,
                              onTap: () => _touched = true,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const Expanded(
          child: TabBarView(
            children: [
              GroupNotificationsList(),
              BookingNotificationsList(),
              MatchNotificationsList(),
            ],
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

/// 分段切換的一半：選中時是浮起來的白色按鈕（薄厚邊、淡陰影），未讀數是橘色圓點；
/// 沒選中時透明、灰字。
class _Segment extends StatelessWidget {
  const _Segment({
    required this.index,
    required this.icon,
    required this.label,
    required this.count,
    required this.onTap,
    super.key,
  });

  final int index;
  final IconData icon;
  final String label;
  final int? count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final controller = DefaultTabController.of(context);
    final badge = unreadBadgeLabel(count);
    final text = Theme.of(context).textTheme;
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final selected = controller.index == index;
        return Semantics(
          selected: selected,
          button: true,
          child: AnimatedContainer(
            duration: AppDurations.press,
            decoration: selected
                ? thickDecoration(
                    color: AppColors.surface,
                    edge: AppColors.cardEdge,
                    radius: AppRadius.pill,
                    thickness: AppSizes.smallThickness,
                    shadow: AppShadows.soft,
                  )
                : BoxDecoration(
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
            child: Material(
              type: MaterialType.transparency,
              shape: const StadiumBorder(),
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: () {
                  onTap();
                  controller.animateTo(index);
                },
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    minHeight: AppSizes.minTouchTarget - AppSpacing.small,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        icon,
                        size: AppSizes.inlineIcon,
                        color: selected
                            ? AppColors.primaryText
                            : AppColors.inkMuted,
                      ),
                      const SizedBox(width: AppSpacing.small),
                      Text(
                        label,
                        style: text.labelLarge!.copyWith(
                          color: selected ? AppColors.ink : AppColors.inkMuted,
                        ),
                      ),
                      if (badge != null) ...[
                        const SizedBox(width: AppSpacing.small),
                        Container(
                          constraints: const BoxConstraints(
                            minWidth: AppSizes.inlineIcon,
                            minHeight: AppSizes.inlineIcon,
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: AppSpacing.xSmall,
                          ),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: selected
                                ? AppColors.primary
                                : AppColors.cardEdge,
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                          ),
                          child: Text(
                            badge,
                            style: text.labelSmall!.copyWith(
                              color: selected
                                  ? AppColors.surface
                                  : AppColors.ink,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
