import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 訂位用的「現在」（UTC）；測試可以換成固定時間（add-booking-notifications D5）。
final bookingClockProvider = Provider<DateTime Function()>(
  (ref) =>
      () => DateTime.now().toUtc(),
);

/// 超時的分鐘數：狀態是已入座（`seated`），而且 [now] 已經超過結束時間 [endAt]
/// 至少 1 分鐘時，回傳超過的整數分鐘；其他情況為 null。
int? overtimeMinutes(String status, String endAt, DateTime now) {
  if (status != 'seated') return null;
  final minutes = now.difference(DateTime.parse(endAt)).inMinutes;
  return minutes >= 1 ? minutes : null;
}
