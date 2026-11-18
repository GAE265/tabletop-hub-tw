import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../domains/booking/data/booking.dart';
import '../../../domains/booking/data/booking_repository.dart';
import '../../../domains/groups/data/group.dart';
import '../../../domains/groups/data/groups_repository.dart';
import '../../../domains/groups/state/current_user.dart';
import '../../../domains/groups/state/group_clock.dart';

/// 首頁「接下來的行程」最多顯示幾筆。
const upcomingLimit = 5;

/// 一次取回多少個即將開始的揪團，再從中找出我已報名的
/// （`GET /api/v1/groups` 沒有「我已加入」的篩選，見 add-home-page design.md）。
const _groupsPageSize = 100;

/// 行程的一列：一筆訂位或一個揪團。
sealed class UpcomingItem {
  const UpcomingItem();

  /// 開始時間（UTC）。
  DateTime get startAt;
}

final class UpcomingBooking extends UpcomingItem {
  const UpcomingBooking(this.booking, {this.shopName});

  final Booking booking;

  /// 對不到店家時為 null。
  final String? shopName;

  @override
  DateTime get startAt => DateTime.parse(booking.startAt).toUtc();
}

final class UpcomingGroup extends UpcomingItem {
  const UpcomingGroup(this.group);

  final Group group;

  @override
  DateTime get startAt => group.startAt.toUtc();
}

/// 每一列右側的狀態。
enum UpcomingStatus {
  /// 已確認的訂位。
  confirmed('已確認'),

  /// 揪團還有名額。
  recruiting('招募中'),

  /// 揪團已額滿（我是成員）。
  full('已額滿'),

  /// 我在這個揪團是候補。
  waitlisted('候補中');

  const UpcomingStatus(this.label);

  final String label;
}

/// 目前使用者即將到來的訂位（已確認）與已報名或候補的揪團，依開始時間由近到遠，最多 [upcomingLimit] 筆。
///
/// - 店家人員查「我的訂位」會得到 403，視為沒有訂位，不算錯誤。
/// - 其他錯誤讓整區進入錯誤狀態，不自動重試；畫面上的「重試」用 `ref.invalidate(upcomingProvider)`。
/// - 切換身分（[currentUserIdProvider] 改變）時重新載入。
final upcomingProvider = FutureProvider.autoDispose<List<UpcomingItem>>((
  ref,
) async {
  ref.watch(currentUserIdProvider);
  final bookingsRepo = ref.watch(bookingRepositoryProvider);
  final groupsRepo = ref.watch(groupsRepositoryProvider);
  final now = ref.watch(groupClockProvider).now().toUtc();

  Future<List<UpcomingItem>> bookings() async {
    final List<Booking> mine;
    try {
      // 後端的 from 是日期；用台灣的今天，已經開始的再由下面過濾掉
      final page = await bookingsRepo.listMine(
        status: 'confirmed',
        fromDate: _taipeiDate(now),
      );
      mine = page.items;
    } on ApiException catch (error) {
      if (error.statusCode == 403) return const [];
      rethrow;
    }
    final upcoming = mine
        .where((b) => b.status == 'confirmed')
        .where((b) => DateTime.parse(b.startAt).isAfter(now))
        .toList();
    if (upcoming.isEmpty) return const [];
    final shops = {
      for (final shop in await bookingsRepo.listShops()) shop.id: shop.name,
    };
    return [
      for (final b in upcoming) UpcomingBooking(b, shopName: shops[b.shopId]),
    ];
  }

  Future<List<UpcomingItem>> groups() async {
    final page = await groupsRepo.list(
      startFrom: now,
      pageSize: _groupsPageSize,
    );
    return [
      for (final g in page.items)
        if (g.status != 'cancelled' &&
            g.startAt.isAfter(now) &&
            (g.myStatus == 'member' || g.myStatus == 'waitlisted'))
          UpcomingGroup(g),
    ];
  }

  // 兩個請求同時發出；任一個失敗就丟出它的錯誤
  final results = await Future.wait([bookings(), groups()]);
  final items = [...results[0], ...results[1]]
    ..sort((a, b) => a.startAt.compareTo(b.startAt));
  return items.take(upcomingLimit).toList();
}, retry: (_, _) => null);

String _taipeiDate(DateTime utc) {
  final t = utc.add(const Duration(hours: 8));
  return '${t.year}-${_two(t.month)}-${_two(t.day)}';
}

String _two(int n) => n.toString().padLeft(2, '0');

/// 第一行：「訂位・19:00・4 人」或「揪團・<名稱>」。
String upcomingTitle(GroupClock clock, UpcomingItem item) => switch (item) {
  UpcomingBooking(:final booking) =>
    '訂位・${_time(clock.toLocal(item.startAt))}・${booking.partySize} 人',
  UpcomingGroup(:final group) => '揪團・${group.title}',
};

/// 第二行：訂位是「店家・桌號 T1、T2」（缺的部分省略）；揪團是「已報名 5 / 7 人」。
String upcomingSubtitle(UpcomingItem item) => switch (item) {
  UpcomingBooking(:final booking, :final shopName) => [
    ?shopName,
    if (booking.tableCodes.isNotEmpty) '桌號 ${booking.tableCodes.join('、')}',
  ].join('・'),
  UpcomingGroup(:final group) =>
    '已報名 ${group.memberCount} / ${group.capacity} 人',
};

UpcomingStatus upcomingStatus(UpcomingItem item) => switch (item) {
  UpcomingBooking() => UpcomingStatus.confirmed,
  UpcomingGroup(:final group) when group.myStatus == 'waitlisted' =>
    UpcomingStatus.waitlisted,
  UpcomingGroup(:final group) when group.remainingSlots <= 0 =>
    UpcomingStatus.full,
  UpcomingGroup() => UpcomingStatus.recruiting,
};

/// 點這一列要去的頁面。
String upcomingRoute(UpcomingItem item) => switch (item) {
  UpcomingBooking() => '/booking/mine',
  UpcomingGroup() => '/groups',
};

/// 日期徽章的月份，例如「11月」。
String upcomingMonthLabel(GroupClock clock, UpcomingItem item) =>
    '${clock.toLocal(item.startAt).month}月';

/// 日期徽章的日，例如「21」。
String upcomingDayLabel(GroupClock clock, UpcomingItem item) =>
    '${clock.toLocal(item.startAt).day}';

String _time(DateTime local) => '${_two(local.hour)}:${_two(local.minute)}';
