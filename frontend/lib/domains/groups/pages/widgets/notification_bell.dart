import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../state/group_notifications_state.dart';

/// 導覽列的通知鈴鐺：有未讀時顯示數字，點下前往通知列表頁。
/// 查詢失敗時只顯示鈴鐺，不顯示數字、不跳錯誤。
class NotificationBell extends ConsumerWidget {
  const NotificationBell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final label = unreadBadgeLabel(ref.watch(groupUnreadCountProvider));
    return IconButton(
      tooltip: label == null ? '通知' : '通知（$label 則未讀）',
      onPressed: () => context.go('/groups/notifications'),
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
