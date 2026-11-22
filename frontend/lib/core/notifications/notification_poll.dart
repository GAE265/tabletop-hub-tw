import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 鈴鐺重新查詢未讀數的間隔；揪團與訂位共用（add-groups-notifications D5、
/// add-booking-notifications D4）。
final notificationPollIntervalProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 60),
);

/// 鈴鐺或分頁上的文字：沒有未讀（或查詢失敗）時為 null，超過 99 顯示「99+」。
String? unreadBadgeLabel(int? count) {
  if (count == null || count <= 0) return null;
  return count > 99 ? '99+' : '$count';
}
