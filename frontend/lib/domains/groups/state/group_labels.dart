import '../data/group.dart';
import '../data/group_notification.dart';
import 'group_clock.dart';

/// 揪團畫面共用的文字格式。參考畫面與正式頁面顯示一致的文字。

String _two(int value) => value.toString().padLeft(2, '0');

const _weekdays = ['一', '二', '三', '四', '五', '六', '日'];

/// 星期幾，例如「六」。
String weekdayLabel(DateTime date) => _weekdays[date.weekday - 1];

/// 例如「2026/11/14」。
String formatDate(DateTime date) => '${date.year}/${date.month}/${date.day}';

/// 例如「13:00 – 15:00」（裝置時區）。
String formatTimeRange(GroupClock clock, Group group) {
  final start = clock.toLocal(group.startAt);
  final end = clock.toLocal(group.endAt);
  return '${_two(start.hour)}:${_two(start.minute)} – '
      '${_two(end.hour)}:${_two(end.minute)}';
}

/// 從當天 00:00 起算的時間，例如「19:00」；沒有值時為 null。
String? formatTimeOfDay(Duration? value) {
  if (value == null) return null;
  return '${_two(value.inHours)}:${_two(value.inMinutes.remainder(60))}';
}

/// 沒填寫時不顯示；0 元顯示「免費」。
String? feeLabel(int? fee) {
  if (fee == null) return null;
  return fee == 0 ? '免費' : '\$$fee／人';
}

/// 開放中且開團主已確定成團。已取消或已結束時，顯示原本的狀態。
bool isConfirmedOpen(Group group) =>
    group.confirmedAt != null && group.status == 'open';

/// 通知的一句說明，例如「「週末輕策略」已成團」。
String notificationText(GroupNotification notification) {
  final title = '「${notification.group.title}」';
  return switch (notification.type) {
    'group_confirmed' => '$title已成團',
    'group_cancelled' => '$title已取消',
    'waitlist_promoted' => '你已從候補遞補為$title的成員',
    _ => '$title有新的消息',
  };
}

/// 例如「11/14 11:05」（裝置時區）。
String formatShortDateTime(GroupClock clock, DateTime instant) {
  final wall = clock.toLocal(instant);
  return '${wall.month}/${wall.day} ${_two(wall.hour)}:${_two(wall.minute)}';
}

/// 例如「19:00」（裝置時區）。
String formatClockTime(GroupClock clock, DateTime instant) {
  final wall = clock.toLocal(instant);
  return '${_two(wall.hour)}:${_two(wall.minute)}';
}
