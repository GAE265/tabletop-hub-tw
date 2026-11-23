import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/notification_widgets.dart';
import '../../../../core/notifications/notification_day.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../data/group_notification.dart';
import '../../state/group_clock.dart';
import '../../state/group_labels.dart';
import '../../state/group_notifications_state.dart';
import '../group_detail_page.dart';
import 'group_widgets.dart';

/// 揪團通知列表（通知頁的「揪團」分頁，add-booking-notifications D4）：
/// 新的在前，捲到底自動載入下一頁；點一則標成已讀並前往該揪團。
class GroupNotificationsList extends ConsumerWidget {
  const GroupNotificationsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupNotificationsProvider);
    final notifier = ref.read(groupNotificationsProvider.notifier);
    final clock = ref.watch(groupClockProvider);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    return KeyedSubtree(
      key: const Key('group-notifications-list'),
      child: state.items.when(
        skipLoadingOnRefresh: false,
        loading: () => const LoadingIndicator(),
        error: (error, _) => Center(
          child: LoadError(error: error, onRetry: notifier.reload),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text('目前沒有通知'))
            : Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: maxWidth),
                  child: NotificationListener<ScrollNotification>(
                    // 接近底部時載入下一頁
                    onNotification: (notification) {
                      if (notification.metrics.extentAfter <
                          AppSizes.loadMoreThreshold) {
                        notifier.loadMore();
                      }
                      return false;
                    },
                    child: ListView(
                      padding: EdgeInsets.fromLTRB(
                        AppSpacing.medium,
                        AppSpacing.medium,
                        AppSpacing.medium,
                        AppSpacing.medium +
                            MediaQuery.paddingOf(context).bottom,
                      ),
                      children: [
                        // 依日期分段：今天／昨天／更早之前（台灣時間）
                        ...groupNotificationsByDay(
                          items: items,
                          dayOf: (n) => notificationDay(
                            clock.toLocal(n.createdAt),
                            clock.toLocal(clock.now()),
                          ),
                          itemBuilder: (n) =>
                              _NotificationTile(notification: n),
                        ),
                        if (state.hasMore) const LoadingIndicator(),
                      ],
                    ),
                  ),
                ),
              ),
      ),
    );
  }
}

class _NotificationTile extends ConsumerWidget {
  const _NotificationTile({required this.notification});

  final GroupNotification notification;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final start = clock.toLocal(notification.group.startAt);

    Future<void> open() async {
      await ref.read(groupNotificationsProvider.notifier).open(notification);
      if (!context.mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupDetailPage(groupId: notification.group.id),
        ),
      );
    }

    return NotificationCard(
      key: Key('notification-${notification.id}'),
      unread: notification.readAt == null,
      unreadDotKey: Key('notification-unread-${notification.id}'),
      tag: _tagFor(notification.type),
      title: notificationText(notification),
      chips: [
        (
          Icons.schedule,
          '揪團時間 ${formatDate(start)}（${weekdayLabel(start)}） '
              '${formatClockTime(clock, notification.group.startAt)}',
        ),
      ],
      footnote: '通知時間 ${formatShortDateTime(clock, notification.createdAt)}',
      onTap: open,
    );
  }
}

/// 種類標籤：（文字, 色調, 圖示）。
(String, PillTone, IconData) _tagFor(String type) => switch (type) {
  'group_confirmed' => ('已成團', PillTone.players, Icons.check_circle_outline),
  'group_cancelled' => ('揪團已取消', PillTone.neutral, Icons.event_busy_outlined),
  'waitlist_promoted' => ('遞補成功', PillTone.accent, Icons.how_to_reg_outlined),
  _ => ('揪團消息', PillTone.neutral, Icons.notifications_outlined),
};
