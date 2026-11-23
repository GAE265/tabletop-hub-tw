// 通知依日期分段（Stitch 版面：今天／昨天／更早之前）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/notifications/notification_day.dart';

void main() {
  final now = DateTime(2026, 11, 14, 12);

  test('同一天是今天（包含午夜剛過）', () {
    expect(
      notificationDay(DateTime(2026, 11, 14, 0, 1), now),
      NotificationDay.today,
    );
    expect(
      notificationDay(DateTime(2026, 11, 14, 11, 59), now),
      NotificationDay.today,
    );
  });

  test('前一天是昨天', () {
    expect(
      notificationDay(DateTime(2026, 11, 13, 23, 59), now),
      NotificationDay.yesterday,
    );
    expect(
      notificationDay(DateTime(2026, 11, 13, 0, 0), now),
      NotificationDay.yesterday,
    );
  });

  test('再之前是更早之前', () {
    expect(
      notificationDay(DateTime(2026, 11, 12, 23, 59), now),
      NotificationDay.earlier,
    );
  });

  test('跨月也算得對', () {
    expect(
      notificationDay(DateTime(2026, 11, 30, 20), DateTime(2026, 12, 1, 9)),
      NotificationDay.yesterday,
    );
  });

  test('分段標題', () {
    expect(NotificationDay.today.label, '今天');
    expect(NotificationDay.yesterday.label, '昨天');
    expect(NotificationDay.earlier.label, '更早之前');
  });
}
