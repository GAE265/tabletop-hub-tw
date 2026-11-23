/// 通知列表的日期分段（揪團與訂位共用）。
enum NotificationDay {
  /// 和現在同一天。
  today('今天'),

  /// 前一天。
  yesterday('昨天'),

  /// 再之前。
  earlier('更早之前');

  const NotificationDay(this.label);

  /// 分段標題，例如「今天」。
  final String label;
}

/// 通知時間 [created] 屬於哪一段；兩個時間都要是同一個時區的當地時間（例如台灣時間）。
NotificationDay notificationDay(DateTime created, DateTime now) {
  final today = DateTime(now.year, now.month, now.day);
  final day = DateTime(created.year, created.month, created.day);
  final diff = today.difference(day).inDays;
  if (diff <= 0) return NotificationDay.today;
  if (diff == 1) return NotificationDay.yesterday;
  return NotificationDay.earlier;
}
