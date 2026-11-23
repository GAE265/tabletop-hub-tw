import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../domains/booking/data/booking.dart';
import '../../../domains/booking/data/booking_repository.dart';
import '../../../domains/groups/data/group.dart';
import '../../../domains/groups/data/groups_repository.dart';
import '../../../domains/groups/state/current_user.dart';
import '../../../domains/groups/state/group_clock.dart';
import '../../../domains/groups/state/group_labels.dart';

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

/// 一張行程卡片要顯示的文字（Stitch 版面）。
class UpcomingCard {
  const UpcomingCard({
    required this.kind,
    required this.title,
    required this.subtitle,
    required this.when,
    required this.people,
    required this.footer,
    required this.action,
  });

  /// 最上面的小標：「訂位」或「揪團」。
  final String kind;

  /// 大標題：訂位是店家名稱（對不到時是「訂位」），揪團是揪團名稱。
  final String title;

  /// 標題下方：訂位是「桌號 T1、T2」（沒有桌號時是空字串），揪團是「開團主：名字・店家」。
  final String subtitle;

  /// 台灣時間，例如「11/21（六）19:00–21:00」。
  final String when;

  /// 訂位是「4 人」，揪團是「5 / 7 人」。
  final String people;

  /// 卡片最下面左邊：訂位代碼；揪團是剩餘名額，額滿時是候補人數。
  final String footer;

  /// 卡片最下面右邊的連結文字。
  final String action;
}

UpcomingCard upcomingCard(GroupClock clock, UpcomingItem item) {
  final when = _range(
    clock.toLocal(item.startAt),
    clock.toLocal(switch (item) {
      UpcomingBooking(:final booking) => DateTime.parse(booking.endAt).toUtc(),
      UpcomingGroup(:final group) => group.endAt.toUtc(),
    }),
  );
  return switch (item) {
    UpcomingBooking(:final booking, :final shopName) => UpcomingCard(
      kind: '訂位',
      title: shopName ?? '訂位',
      subtitle: booking.tableCodes.isEmpty
          ? ''
          : '桌號 ${booking.tableCodes.join('、')}',
      when: when,
      people: '${booking.partySize} 人',
      footer: '訂位代碼 ${booking.reservationCode}',
      action: '查看我的訂位',
    ),
    UpcomingGroup(:final group) => UpcomingCard(
      kind: '揪團',
      title: group.title,
      subtitle: '開團主：${group.organizer.displayName}・${group.shop.name}',
      when: when,
      people: '${group.memberCount} / ${group.capacity} 人',
      footer: group.remainingSlots > 0
          ? '還有 ${group.remainingSlots} 個名額'
          // 「已額滿」已經在狀態標籤上，這裡只寫候補人數
          : group.waitlistCount > 0
          ? '候補 ${group.waitlistCount} 人'
          : '目前沒有候補',
      action: '查看揪團',
    ),
  };
}

/// 例如「11/21（六）19:00–21:00」。
String _range(DateTime start, DateTime end) =>
    '${start.month}/${start.day}（${weekdayLabel(start)}）'
    '${_time(start)}–${_time(end)}';

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
  UpcomingGroup(:final group) => '/groups/${group.id}',
};

String _time(DateTime local) => '${_two(local.hour)}:${_two(local.minute)}';
