import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/notification_widgets.dart';
import '../../../../core/notifications/notification_day.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../../../core/api/api_exception.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../data/booking_notification.dart';
import '../../state/booking_notifications_state.dart';
import '../../state/booking_overtime.dart';

/// 訂位通知列表（通知頁的「訂位」分頁，add-booking-notifications D4）：
/// 新的在前，捲到底自動載入下一頁；點一則標成已讀，玩家前往我的訂位、店家人員前往店家看板。
class BookingNotificationsList extends ConsumerWidget {
  const BookingNotificationsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(bookingNotificationsProvider);
    final notifier = ref.read(bookingNotificationsProvider.notifier);
    final now = ref.watch(bookingClockProvider)();
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    const loading = Padding(
      padding: EdgeInsets.all(AppSpacing.large),
      child: Center(child: CircularProgressIndicator()),
    );
    return KeyedSubtree(
      key: const Key('booking-notifications-list'),
      child: state.items.when(
        skipLoadingOnRefresh: false,
        loading: () => loading,
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  error is ApiException ? error.message : '發生未知錯誤',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.medium),
                FilledButton(
                  onPressed: notifier.reload,
                  child: const Text('重試'),
                ),
              ],
            ),
          ),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text('目前沒有訂位通知'))
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
                            bookingTaipeiTime(n.createdAt),
                            bookingTaipeiTime(now),
                          ),
                          itemBuilder: (n) =>
                              _NotificationTile(notification: n),
                        ),
                        if (state.hasMore) loading,
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

  final BookingNotification notification;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final b = notification.booking;

    Future<void> open() async {
      await ref.read(bookingNotificationsProvider.notifier).open(notification);
      if (!context.mounted) return;
      context.go(bookingNotificationRoute(notification));
    }

    final shopNew = notification.type == 'shop_new_booking';
    return NotificationCard(
      key: Key('booking-notification-${notification.id}'),
      unread: notification.readAt == null,
      unreadDotKey: Key('booking-notification-unread-${notification.id}'),
      tag: shopNew
          ? ('新訂位', PillTone.duration, Icons.storefront_outlined)
          : ('訂位成功', PillTone.players, Icons.event_available_outlined),
      title: bookingNotificationText(notification),
      chips: [
        (
          Icons.schedule,
          '訂位時間 ${bookingNotificationDate(b.startAt)}'
              '${bookingNotificationClock(b.startAt)}–'
              '${bookingNotificationClock(b.endAt)}',
        ),
        (Icons.storefront_outlined, b.shopName),
        (Icons.group_outlined, '${b.partySize} 人'),
        (Icons.confirmation_number_outlined, b.reservationCode),
      ],
      footnote:
          '通知時間 ${bookingNotificationShortDateTime(notification.createdAt)}',
      onTap: open,
    );
  }
}
