import '../data/group.dart';
import 'group_clock.dart';

/// 開團主替揪團訂位：產生帶好揪團資料的訂位頁網址（`/booking?...`）。
///
/// - 人數帶預計人數（capacity），先把整團的位子訂好。
/// - 訂位頁的時段每 30 分鐘一格：開始時間往前、結束時間往後取到半點，保證涵蓋整場揪團；
///   結束超過當天最後一格（例如跨過午夜）時取 23:30，由開團主自行調整。
/// - 特殊需求帶「揪團：<名稱>」，方便店家知道是哪一團。
Uri groupBookingLink(GroupClock clock, Group group) {
  final start = clock.toLocal(group.startAt);
  final end = clock.toLocal(group.endAt);
  final startMinutes = start.hour * 60 + start.minute;
  final sameDay =
      end.year == start.year &&
      end.month == start.month &&
      end.day == start.day;
  final endMinutes = sameDay ? end.hour * 60 + end.minute : _lastSlot;
  return Uri(
    path: '/booking',
    queryParameters: {
      'shop_id': group.shop.id,
      'date': '${start.year}-${_two(start.month)}-${_two(start.day)}',
      'start': _hm(startMinutes ~/ _slot * _slot),
      'end': _hm(_ceilSlot(endMinutes).clamp(0, _lastSlot)),
      'party_size': '${group.capacity}',
      'requests': '揪團：${group.title}',
    },
  );
}

const _slot = 30;
const _lastSlot = 24 * 60 - _slot;

int _ceilSlot(int minutes) => (minutes + _slot - 1) ~/ _slot * _slot;

String _hm(int minutes) => '${_two(minutes ~/ 60)}:${_two(minutes % 60)}';

String _two(int n) => n.toString().padLeft(2, '0');
