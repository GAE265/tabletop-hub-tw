import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domains/booking/state/booking_notifications_state.dart';
import '../theme/app_colors.dart';
import '../theme/thick_widgets.dart';
import '../../domains/groups/state/group_notifications_state.dart';
import '../../domains/matches/state/match_notifications_state.dart';

/// 揪團、訂位與戰績的未讀數總和；三邊都查詢失敗時為 null，有一邊失敗時只算其他邊
/// （add-booking-notifications D4；戰績見 feature-matches-notifications）。
final totalUnreadCountProvider = Provider<int?>((ref) {
  final counts = [
    ref.watch(groupUnreadCountProvider),
    ref.watch(bookingUnreadCountProvider),
    ref.watch(matchUnreadCountProvider),
  ];
  if (counts.every((c) => c == null)) return null;
  return counts.fold<int>(0, (sum, c) => sum + (c ?? 0));
});

/// 導覽列的通知鈴鐺：有未讀時顯示揪團、訂位與戰績的總數，點下前往通知頁 `/notifications`。
/// 查詢失敗時只顯示鈴鐺，不顯示數字、不跳錯誤。
///
/// [thick] 時是有厚度、按得下去的白色圓形按鈕（手機頂部列）。
class NotificationBell extends ConsumerWidget {
  const NotificationBell({this.thick = false, super.key});

  final bool thick;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final label = unreadBadgeLabel(ref.watch(totalUnreadCountProvider));
    final tooltip = label == null ? '通知' : '通知（$label 則未讀）';
    void open() => context.go('/notifications');
    final icon = Badge(
      isLabelVisible: label != null,
      label: label == null
          ? null
          : Text(label, key: const Key('notification-bell-count')),
      child: const Icon(Icons.notifications_outlined, color: AppColors.ink),
    );
    if (thick) {
      return ThickIconButton(icon: icon, tooltip: tooltip, onPressed: open);
    }
    return IconButton(tooltip: tooltip, onPressed: open, icon: icon);
  }
}
