import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/notification_widgets.dart';
import '../../../../core/api/api_exception.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../../../core/notifications/notification_day.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/match_notification.dart';
import '../../state/match_notifications_state.dart';
import 'match_widgets.dart';

/// 戰績通知列表（通知頁的「戰績」分頁）：新的在前，捲到底自動載入下一頁；
/// 點一則標成已讀，前往那一局的紀錄頁確認結果。
///
/// 樣式只用 `app/theme/` 的共用元件與 token（AGENTS.md 5.4），跟揪團、訂位的列表一致。
class MatchNotificationsList extends ConsumerWidget {
  const MatchNotificationsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(matchNotificationsProvider);
    final notifier = ref.read(matchNotificationsProvider.notifier);
    final now = ref.watch(matchNotificationsClockProvider)();
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    const loading = Padding(
      padding: EdgeInsets.all(AppSpacing.large),
      child: Center(child: CircularProgressIndicator()),
    );
    return KeyedSubtree(
      key: const Key('match-notifications-list'),
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
            ? const Center(child: Text('目前沒有戰績通知'))
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
                            matchTaipeiTime(n.createdAt),
                            matchTaipeiTime(now),
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

  final MatchNotification notification;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    Future<void> open() async {
      await ref.read(matchNotificationsProvider.notifier).open(notification);
      if (!context.mounted) return;
      context.go(matchNotificationRoute(notification));
    }

    return NotificationCard(
      key: Key('match-notification-${notification.id}'),
      unread: notification.readAt == null,
      unreadDotKey: Key('match-notification-unread-${notification.id}'),
      tag: ('請確認結果', PillTone.accent, Icons.emoji_events_outlined),
      title: matchNotificationText(notification),
      chips: [
        (
          Icons.calendar_today_outlined,
          formatPlayedOn(notification.match.playedOn),
        ),
        (Icons.person_outline, '記錄者 ${notification.recordedBy.displayName}'),
      ],
      footnote:
          '通知時間 ${matchNotificationShortDateTime(notification.createdAt)}',
      onTap: open,
    );
  }
}
