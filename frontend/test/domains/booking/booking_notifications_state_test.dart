// 訂位通知的 state 與超時計算（spec：add-booking-notifications 的
// notifications-page、booking-board-overtime）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/state/booking_notifications_state.dart';
import 'package:tabletop_hub/domains/booking/state/booking_overtime.dart';

import '../../support/fakes.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');
const player = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');

/// 台灣時間 11/14 12:00。
final nowUtc = DateTime.utc(2026, 11, 14, 4);

ProviderContainer makeContainer(FakeBookingRepository repo) {
  final container = ProviderContainer(
    overrides: [
      bookingRepositoryProvider.overrideWithValue(repo),
      currentDevUserProvider.overrideWithValue(player),
      bookingClockProvider.overrideWithValue(() => nowUtc),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('鈴鐺的訂位未讀數', () {
    test('啟動時查詢一次，只查一筆', () async {
      final repo = FakeBookingRepository()
        ..notifications = [
          fakeBookingNotification(id: 'bn-1'),
          fakeBookingNotification(id: 'bn-2', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      container.read(bookingUnreadCountProvider);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(bookingUnreadCountProvider), 1);
      expect(repo.notificationCalls.single.pageSize, 1);
    });

    test('查詢失敗：沒有數字（null），不丟出錯誤', () async {
      final repo = FakeBookingRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      container.read(bookingUnreadCountProvider);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(bookingUnreadCountProvider), isNull);
    });
  });

  group('訂位通知列表', () {
    test('載入第一頁，並更新鈴鐺的未讀數', () async {
      final repo = FakeBookingRepository()
        ..notifications = [
          fakeBookingNotification(id: 'bn-2'),
          fakeBookingNotification(id: 'bn-1', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      final state = container.read(bookingNotificationsProvider);
      expect(state.items.value!.map((n) => n.id), ['bn-2', 'bn-1']);
      expect(state.hasMore, isFalse);
      expect(container.read(bookingUnreadCountProvider), 1);
    });

    test('載入失敗後重新載入', () async {
      final repo = FakeBookingRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      expect(
        container.read(bookingNotificationsProvider).items.hasError,
        isTrue,
      );

      repo
        ..notificationsError = null
        ..notifications = [fakeBookingNotification()];
      await notifier.reload();
      expect(
        container.read(bookingNotificationsProvider).items.value,
        hasLength(1),
      );
    });

    test('下一頁接在後面', () async {
      final repo = FakeBookingRepository()
        ..notifications = [
          for (var i = 25; i >= 1; i--) fakeBookingNotification(id: 'bn-$i'),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      expect(
        container.read(bookingNotificationsProvider).items.value,
        hasLength(20),
      );
      expect(container.read(bookingNotificationsProvider).hasMore, isTrue);

      await notifier.loadMore();
      final state = container.read(bookingNotificationsProvider);
      expect(state.items.value, hasLength(25));
      expect(state.hasMore, isFalse);
      expect(repo.notificationCalls.last, (page: 2, pageSize: 20));
    });

    test('點未讀的通知：標成已讀，鈴鐺少 1', () async {
      final repo = FakeBookingRepository()
        ..notifications = [
          fakeBookingNotification(id: 'bn-2'),
          fakeBookingNotification(id: 'bn-1'),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      final first = container
          .read(bookingNotificationsProvider)
          .items
          .value!
          .first;

      await notifier.open(first);
      expect(repo.markReadCalls, ['bn-2']);
      expect(
        container.read(bookingNotificationsProvider).items.value!.first.readAt,
        isNotNull,
      );
      expect(container.read(bookingUnreadCountProvider), 1);
    });

    test('點已讀的通知：不送出', () async {
      final repo = FakeBookingRepository()
        ..notifications = [fakeBookingNotification(readAt: nowUtc)];
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      await notifier.open(
        container.read(bookingNotificationsProvider).items.value!.single,
      );
      expect(repo.markReadCalls, isEmpty);
    });

    test('標成已讀失敗：改回未讀，鈴鐺數字還原', () async {
      final repo = FakeBookingRepository()
        ..notifications = [fakeBookingNotification()]
        ..markReadError = failure;
      final container = makeContainer(repo);
      final notifier = container.read(bookingNotificationsProvider.notifier);
      await notifier.loaded;
      await notifier.open(
        container.read(bookingNotificationsProvider).items.value!.single,
      );
      expect(
        container.read(bookingNotificationsProvider).items.value!.single.readAt,
        isNull,
      );
      expect(container.read(bookingUnreadCountProvider), 1);
    });
  });

  group('通知的文字與前往的頁面', () {
    test('玩家的訂位成功：「你在「店名」的訂位已成功」，前往我的訂位', () {
      final n = fakeBookingNotification(type: 'booking_confirmed');
      expect(bookingNotificationText(n), '你在「甲店」的訂位已成功');
      expect(bookingNotificationRoute(n), '/booking/mine');
    });

    test('店家人員的新訂位：台灣時間與人數，前往店家看板', () {
      final n = fakeBookingNotification(
        type: 'shop_new_booking',
        // 台灣 11/22（日）19:00
        startAt: DateTime.utc(2026, 11, 22, 11),
        partySize: 6,
      );
      expect(bookingNotificationText(n), '新訂位：11/22（日）19:00・6 人');
      expect(bookingNotificationRoute(n), '/booking/board');
    });
  });

  group('超時', () {
    // 結束時間：台灣 19:00（UTC 11:00）
    const end = '2026-11-25T11:00:00Z';

    test('已入座、超過結束時間：回傳超過的分鐘數', () {
      expect(
        overtimeMinutes('seated', end, DateTime.utc(2026, 11, 25, 11, 25)),
        25,
      );
      expect(
        overtimeMinutes('seated', end, DateTime.utc(2026, 11, 25, 11, 1)),
        1,
      );
    });

    test('還沒到結束時間、或超過不到 1 分鐘：不算超時', () {
      expect(
        overtimeMinutes('seated', end, DateTime.utc(2026, 11, 25, 10, 50)),
        isNull,
      );
      expect(
        overtimeMinutes('seated', end, DateTime.utc(2026, 11, 25, 11, 0, 30)),
        isNull,
      );
    });

    test('不是已入座：不算超時', () {
      final later = DateTime.utc(2026, 11, 25, 12);
      for (final status in ['confirmed', 'completed', 'cancelled', 'no_show']) {
        expect(overtimeMinutes(status, end, later), isNull, reason: status);
      }
    });
  });
}
