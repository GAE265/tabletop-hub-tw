import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domains/booking/state/booking_notifications_state.dart';
import '../../domains/groups/state/group_notifications_state.dart';

/// 揪團與訂位的未讀數總和；兩邊都查詢失敗時為 null，只有一邊失敗時只算另一邊
/// （add-booking-notifications D4）。
final totalUnreadCountProvider = Provider<int?>((ref) {
  final groups = ref.watch(groupUnreadCountProvider);
  final bookings = ref.watch(bookingUnreadCountProvider);
  if (groups == null && bookings == null) return null;
  return (groups ?? 0) + (bookings ?? 0);
});

/// 導覽列的通知鈴鐺：有未讀時顯示揪團與訂位的總數，點下前往通知頁 `/notifications`。
/// 查詢失敗時只顯示鈴鐺，不顯示數字、不跳錯誤。
class NotificationBell extends ConsumerWidget {
  const NotificationBell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final label = unreadBadgeLabel(ref.watch(totalUnreadCountProvider));
    return IconButton(
      tooltip: label == null ? '通知' : '通知（$label 則未讀）',
      onPressed: () => context.go('/notifications'),
      icon: Badge(
        isLabelVisible: label != null,
        label: label == null
            ? null
            : Text(label, key: const Key('notification-bell-count')),
        child: const Icon(Icons.notifications_outlined),
      ),
    );
  }
}
