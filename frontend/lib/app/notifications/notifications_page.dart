import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/booking/pages/widgets/booking_notifications_list.dart';
import '../../domains/booking/state/booking_notifications_state.dart';
import '../../domains/groups/pages/widgets/group_notifications_list.dart';
import '../../domains/groups/state/group_notifications_state.dart';
import '../theme/app_spacing.dart';

/// 通知頁 `/notifications`：「揪團」「訂位」兩個分頁（add-booking-notifications D4）。
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
    return Scaffold(
      key: const Key('notifications-page'),
      appBar: AppBar(
        title: const Text('通知'),
        bottom: TabBar(
          onTap: (_) => _touched = true,
          tabs: [
            _TabLabel(
              key: const Key('notifications-tab-groups'),
              label: '揪團',
              count: groups,
            ),
            _TabLabel(
              key: const Key('notifications-tab-booking'),
              label: '訂位',
              count: bookings,
            ),
          ],
        ),
      ),
      body: const TabBarView(
        children: [GroupNotificationsList(), BookingNotificationsList()],
      ),
    );
  }
}

class _TabLabel extends StatelessWidget {
  const _TabLabel({required this.label, required this.count, super.key});

  final String label;
  final int? count;

  @override
  Widget build(BuildContext context) {
    final badge = unreadBadgeLabel(count);
    return Tab(
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label),
          if (badge != null) ...[
            const SizedBox(width: AppSpacing.xSmall),
            Badge(label: Text(badge)),
          ],
        ],
      ),
    );
  }
}
