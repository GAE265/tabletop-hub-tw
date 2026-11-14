import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 揪團畫面用的時間與時區換算。後端一律是 UTC，畫面一律用裝置時區的「牆上時間」。
///
/// 包成介面是為了讓測試固定在 UTC+8，結果不受執行測試的電腦時區影響。
abstract interface class GroupClock {
  /// 現在時間（UTC）。
  DateTime now();

  /// UTC 時間 → 裝置時區的牆上時間。
  DateTime toLocal(DateTime instant);

  /// 裝置時區的牆上時間（例如月曆上某天的 00:00）→ UTC。
  DateTime fromLocal(DateTime wall);
}

class SystemGroupClock implements GroupClock {
  const SystemGroupClock();

  @override
  DateTime now() => DateTime.now().toUtc();

  @override
  DateTime toLocal(DateTime instant) => instant.toLocal();

  @override
  DateTime fromLocal(DateTime wall) => DateTime(
    wall.year,
    wall.month,
    wall.day,
    wall.hour,
    wall.minute,
    wall.second,
  ).toUtc();
}

final groupClockProvider = Provider<GroupClock>(
  (ref) => const SystemGroupClock(),
);

/// 只取日期（牆上時間的年月日），當作月曆的 key。
DateTime dateOnly(DateTime wall) => DateTime(wall.year, wall.month, wall.day);
