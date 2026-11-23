import '../data/booking.dart';
import 'booking_overtime.dart';

/// 店家看板訂位列表的篩選（Stitch 版面）。
enum BoardFilter {
  /// 全部。
  all,

  /// 已入座且超過結束時間。
  overtime,

  /// 已入座、還沒超時（進行中）。
  seated,

  /// 已確認、還沒到店（待到店）。
  waiting,
}

bool _isOvertime(Booking b, DateTime now) =>
    overtimeMinutes(b.status, b.endAt, now) != null;

bool _matches(Booking b, BoardFilter filter, DateTime now) => switch (filter) {
  BoardFilter.all => true,
  BoardFilter.overtime => _isOvertime(b, now),
  BoardFilter.seated => b.status == 'seated' && !_isOvertime(b, now),
  BoardFilter.waiting => b.status == 'confirmed',
};

/// 依篩選過濾，保持原本順序；[now] 是 UTC，用來判斷是否超時。
List<Booking> filterBoard(
  List<Booking> bookings,
  BoardFilter filter,
  DateTime now,
) => [
  for (final b in bookings)
    if (_matches(b, filter, now)) b,
];

/// 某個篩選有幾筆（篩選膠囊上的數字）。
int boardCount(List<Booking> bookings, BoardFilter filter, DateTime now) =>
    filterBoard(bookings, filter, now).length;

/// 已入座、還沒到結束時間 [endAt] 時，距離結束還有幾分鐘（不足一分鐘算一分鐘）；
/// 其他情況為 null。
int? remainingMinutes(String status, String endAt, DateTime now) {
  if (status != 'seated') return null;
  final left = DateTime.parse(endAt).difference(now);
  if (left <= Duration.zero) return null;
  return (left.inSeconds + 59) ~/ 60;
}

/// 店家看板上方的統計。
class BoardStats {
  const BoardStats({
    required this.total,
    required this.inUse,
    required this.overtime,
    required this.free,
  });

  /// 全店桌數（座位圖上不重複的桌子）。
  final int total;

  /// 使用中：已入座的訂位數（包含已超時）。
  final int inUse;

  /// 已超時的訂位數。
  final int overtime;

  /// 空桌：全店桌數扣掉已入座訂位佔用的桌子。
  final int free;
}

BoardStats boardStats(
  List<SeatingPlan> plans,
  List<Booking> bookings,
  DateTime now,
) {
  final tables = {
    for (final plan in plans)
      for (final t in plan.tables) t.tableCode,
  };
  final seated = bookings.where((b) => b.status == 'seated').toList();
  final busy = {
    for (final b in seated)
      for (final code in b.tableCodes)
        if (tables.contains(code)) code,
  };
  return BoardStats(
    total: tables.length,
    inUse: seated.length,
    overtime: seated.where((b) => _isOvertime(b, now)).length,
    free: tables.length - busy.length,
  );
}
