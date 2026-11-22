import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../core/api/api_exception.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../data/booking_notification.dart';
import '../../state/booking_notifications_state.dart';

/// 訂位通知列表（通知頁的「訂位」分頁，add-booking-notifications D4）：
/// 新的在前，捲到底自動載入下一頁；點一則標成已讀，玩家前往我的訂位、店家人員前往店家看板。
class BookingNotificationsList extends ConsumerWidget {
  const BookingNotificationsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(bookingNotificationsProvider);
    final notifier = ref.read(bookingNotificationsProvider.notifier);
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
                    child: ListView.separated(
                      padding: const EdgeInsets.symmetric(
                        vertical: AppSpacing.small,
                      ),
                      itemCount: items.length + (state.hasMore ? 1 : 0),
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) => index == items.length
                          ? loading
                          : _NotificationTile(notification: items[index]),
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
    final unread = notification.readAt == null;
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(color: AppColors.inkMuted);
    final b = notification.booking;

    Future<void> open() async {
      await ref.read(bookingNotificationsProvider.notifier).open(notification);
      if (!context.mounted) return;
      context.go(bookingNotificationRoute(notification));
    }

    return Material(
      key: Key('booking-notification-${notification.id}'),
      color: unread ? AppColors.primaryTint : AppColors.surface,
      child: InkWell(
        onTap: open,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                notification.type == 'shop_new_booking'
                    ? Icons.storefront_outlined
                    : Icons.event_available_outlined,
                color: AppColors.inkMuted,
              ),
              const SizedBox(width: AppSpacing.medium),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      bookingNotificationText(notification),
                      style: text.bodyLarge!.copyWith(
                        fontWeight: unread ? FontWeight.w700 : FontWeight.w400,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xSmall),
                    // 兩段各自換行，不會把日期和時間拆到兩行
                    Wrap(
                      spacing: AppSpacing.medium,
                      children: [
                        Text(
                          '訂位時間 ${bookingNotificationDate(b.startAt)}'
                          '${bookingNotificationClock(b.startAt)}–'
                          '${bookingNotificationClock(b.endAt)}',
                          style: muted,
                        ),
                        Text(
                          '通知時間 '
                          '${bookingNotificationShortDateTime(notification.createdAt)}',
                          style: muted,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (unread)
                Padding(
                  padding: const EdgeInsets.only(left: AppSpacing.small),
                  child: Container(
                    key: Key('booking-notification-unread-${notification.id}'),
                    width: AppSizes.unreadDot,
                    height: AppSizes.unreadDot,
                    decoration: const BoxDecoration(
                      color: AppColors.primary,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
