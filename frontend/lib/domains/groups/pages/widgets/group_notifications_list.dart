import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
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
                    child: ListView.separated(
                      padding: const EdgeInsets.symmetric(
                        vertical: AppSpacing.small,
                      ),
                      itemCount: items.length + (state.hasMore ? 1 : 0),
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) => index == items.length
                          ? const LoadingIndicator()
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

  final GroupNotification notification;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final unread = notification.readAt == null;
    final text = Theme.of(context).textTheme;
    final start = clock.toLocal(notification.group.startAt);
    final muted = text.bodySmall!.copyWith(color: AppColors.inkMuted);

    Future<void> open() async {
      await ref.read(groupNotificationsProvider.notifier).open(notification);
      if (!context.mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupDetailPage(groupId: notification.group.id),
        ),
      );
    }

    return Material(
      key: Key('notification-${notification.id}'),
      color: unread ? AppColors.primaryTint : AppColors.surface,
      child: InkWell(
        onTap: open,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(_iconFor(notification.type), color: AppColors.inkMuted),
              const SizedBox(width: AppSpacing.medium),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notificationText(notification),
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
                          '揪團時間 ${formatDate(start)}（${weekdayLabel(start)}） '
                          '${formatClockTime(clock, notification.group.startAt)}',
                          style: muted,
                        ),
                        Text(
                          '通知時間 '
                          '${formatShortDateTime(clock, notification.createdAt)}',
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
                    key: Key('notification-unread-${notification.id}'),
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

IconData _iconFor(String type) => switch (type) {
  'group_confirmed' => Icons.check_circle_outline,
  'group_cancelled' => Icons.event_busy_outlined,
  'waitlist_promoted' => Icons.how_to_reg_outlined,
  _ => Icons.notifications_outlined,
};
