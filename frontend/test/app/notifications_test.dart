// 合併的通知鈴鐺、通知頁的兩個分頁、訂位通知列表
// （spec：add-booking-notifications 的 notifications-page）。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/notifications/notification_bell.dart';
import 'package:tabletop_hub/app/notifications/notifications_page.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/state/booking_overtime.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/current_user.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../domains/groups/support.dart';
import '../support/fakes.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');
const player = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');

/// `/` 放鈴鐺，`/notifications` 是通知頁，`/booking/mine`、`/booking/board` 是假頁面。
Future<GoRouter> pumpNotifications(
  WidgetTester tester, {
  FakeGroupsRepository? groups,
  FakeBookingRepository? bookings,
  String location = '/',
}) async {
  tester.view.physicalSize = const Size(400, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  Widget stub(String text) => Scaffold(body: Center(child: Text(text)));
  final router = GoRouter(
    initialLocation: location,
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const Scaffold(
          body: Center(child: NotificationBell(key: Key('bell'))),
        ),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsPage(),
      ),
      GoRoute(
        path: '/booking/mine',
        builder: (context, state) => stub('我的訂位頁'),
      ),
      GoRoute(
        path: '/booking/board',
        builder: (context, state) => stub('店家看板頁'),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        groupsRepositoryProvider.overrideWithValue(
          groups ?? FakeGroupsRepository(),
        ),
        groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
        currentUserIdProvider.overrideWithValue('u-player'),
        bookingRepositoryProvider.overrideWithValue(
          bookings ?? FakeBookingRepository(),
        ),
        currentDevUserProvider.overrideWithValue(player),
        bookingClockProvider.overrideWithValue(() => nowUtc),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return router;
}

FakeGroupsRepository groupsUnread(int count) => FakeGroupsRepository()
  ..notifications = [
    for (var i = count; i >= 1; i--) fakeNotification(id: 'n-$i'),
  ];

FakeBookingRepository bookingsUnread(int count) => FakeBookingRepository()
  ..notifications = [
    for (var i = count; i >= 1; i--) fakeBookingNotification(id: 'bn-$i'),
  ];

Finder badgeText(String text) => find.descendant(
  of: find.byKey(const Key('bell')),
  matching: find.text(text),
);

Finder bellCount() => find.byKey(const Key('notification-bell-count'));

void main() {
  group('合併的通知鈴鐺', () {
    testWidgets('揪團 2 則、訂位 1 則：顯示 3', (tester) async {
      await pumpNotifications(
        tester,
        groups: groupsUnread(2),
        bookings: bookingsUnread(1),
      );
      expect(badgeText('3'), findsOneWidget);
    });

    testWidgets('加起來超過 99：顯示 99+', (tester) async {
      await pumpNotifications(
        tester,
        groups: groupsUnread(60),
        bookings: bookingsUnread(50),
      );
      expect(badgeText('99+'), findsOneWidget);
    });

    testWidgets('兩邊都沒有未讀：不顯示數字', (tester) async {
      await pumpNotifications(tester);
      expect(find.byKey(const Key('bell')), findsOneWidget);
      expect(bellCount(), findsNothing);
    });

    testWidgets('揪團查詢失敗：只算訂位，不跳錯誤', (tester) async {
      await pumpNotifications(
        tester,
        groups: FakeGroupsRepository()..notificationsError = failure,
        bookings: bookingsUnread(1),
      );
      expect(badgeText('1'), findsOneWidget);
      expect(find.text('伺服器忙碌中'), findsNothing);
    });

    testWidgets('兩邊都失敗：鈴鐺照常顯示、沒有數字、不跳錯誤', (tester) async {
      await pumpNotifications(
        tester,
        groups: FakeGroupsRepository()..notificationsError = failure,
        bookings: FakeBookingRepository()..notificationsError = failure,
      );
      expect(find.byKey(const Key('bell')), findsOneWidget);
      expect(bellCount(), findsNothing);
      expect(find.text('伺服器忙碌中'), findsNothing);
    });

    testWidgets('每 60 秒重新查詢：訂位多一則，鈴鐺多 1', (tester) async {
      final bookings = bookingsUnread(0);
      await pumpNotifications(
        tester,
        groups: groupsUnread(1),
        bookings: bookings,
      );
      expect(badgeText('1'), findsOneWidget);

      bookings.notifications = [fakeBookingNotification(id: 'bn-new')];
      await tester.pump(const Duration(seconds: 59));
      expect(badgeText('1'), findsOneWidget);
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();
      expect(badgeText('2'), findsOneWidget);
    });

    testWidgets('點鈴鐺：前往 /notifications', (tester) async {
      final router = await pumpNotifications(tester, groups: groupsUnread(1));
      await tester.tap(find.byKey(const Key('bell')));
      await tester.pumpAndSettle();
      expect(router.state.uri.path, '/notifications');
      expect(find.byKey(const Key('notifications-page')), findsOneWidget);
    });
  });

  group('通知頁的分頁', () {
    bool selected(WidgetTester tester, String key) {
      final controller = DefaultTabController.of(
        tester.element(find.byKey(Key(key))),
      );
      final index = key == 'notifications-tab-groups' ? 0 : 1;
      return controller.index == index;
    }

    testWidgets('只有訂位有未讀：預設開「訂位」', (tester) async {
      await pumpNotifications(
        tester,
        bookings: bookingsUnread(2),
        location: '/notifications',
      );
      expect(selected(tester, 'notifications-tab-booking'), isTrue);
      expect(
        find.byKey(const Key('booking-notifications-list')),
        findsOneWidget,
      );
    });

    testWidgets('兩邊都有未讀：預設開「揪團」，分頁標題各有數字', (tester) async {
      await pumpNotifications(
        tester,
        groups: groupsUnread(1),
        bookings: bookingsUnread(2),
        location: '/notifications',
      );
      expect(selected(tester, 'notifications-tab-groups'), isTrue);
      expect(find.byKey(const Key('group-notifications-list')), findsOneWidget);
      expect(
        find.descendant(
          of: find.byKey(const Key('notifications-tab-groups')),
          matching: find.text('1'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('notifications-tab-booking')),
          matching: find.text('2'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('都沒有未讀：預設開「揪團」，分頁標題沒有數字', (tester) async {
      await pumpNotifications(tester, location: '/notifications');
      expect(selected(tester, 'notifications-tab-groups'), isTrue);
      expect(
        find.descendant(
          of: find.byKey(const Key('notifications-tab-groups')),
          matching: find.text('0'),
        ),
        findsNothing,
      );
    });

    testWidgets('點「訂位」分頁：顯示訂位通知列表', (tester) async {
      await pumpNotifications(
        tester,
        groups: groupsUnread(1),
        bookings: bookingsUnread(1),
        location: '/notifications',
      );
      await tester.tap(find.byKey(const Key('notifications-tab-booking')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('booking-notifications-list')),
        findsOneWidget,
      );
      expect(find.text('你在「甲店」的訂位已成功'), findsOneWidget);
    });
  });

  group('訂位通知列表', () {
    Future<GoRouter> pumpBookingTab(
      WidgetTester tester,
      FakeBookingRepository bookings,
    ) async {
      final router = await pumpNotifications(
        tester,
        bookings: bookings,
        location: '/notifications',
      );
      await tester.tap(find.byKey(const Key('notifications-tab-booking')));
      await tester.pumpAndSettle();
      return router;
    }

    testWidgets('兩種通知的文字、訂位時間與通知時間，新的在前', (tester) async {
      final bookings = FakeBookingRepository()
        ..notifications = [
          fakeBookingNotification(
            id: 'bn-2',
            type: 'shop_new_booking',
            partySize: 6,
            createdAt: DateTime.utc(2026, 11, 14, 3, 5),
          ),
          fakeBookingNotification(id: 'bn-1', readAt: nowUtc),
        ];
      await pumpBookingTab(tester, bookings);
      const texts = ['新訂位：11/22（日）19:00・6 人', '你在「甲店」的訂位已成功'];
      for (final text in texts) {
        expect(find.text(text), findsOneWidget);
      }
      expect(
        tester.getTopLeft(find.text(texts[0])).dy,
        lessThan(tester.getTopLeft(find.text(texts[1])).dy),
      );
      expect(find.textContaining('訂位時間 11/22（日）19:00–21:00'), findsNWidgets(2));
      expect(find.textContaining('通知時間 11/14 11:05'), findsOneWidget);
    });

    testWidgets('未讀與已讀看得出差別', (tester) async {
      final bookings = FakeBookingRepository()
        ..notifications = [
          fakeBookingNotification(id: 'bn-2'),
          fakeBookingNotification(id: 'bn-1', readAt: nowUtc),
        ];
      await pumpBookingTab(tester, bookings);
      expect(
        find.byKey(const Key('booking-notification-unread-bn-2')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('booking-notification-unread-bn-1')),
        findsNothing,
      );
    });

    testWidgets('玩家點未讀的訂位成功：標成已讀，前往我的訂位', (tester) async {
      final bookings = bookingsUnread(1);
      final router = await pumpBookingTab(tester, bookings);
      await tester.tap(find.text('你在「甲店」的訂位已成功'));
      await tester.pumpAndSettle();
      expect(bookings.markReadCalls, ['bn-1']);
      expect(router.state.uri.path, '/booking/mine');
      expect(find.text('我的訂位頁'), findsOneWidget);
    });

    testWidgets('店家人員點新訂位：前往店家看板', (tester) async {
      final bookings = FakeBookingRepository()
        ..notifications = [fakeBookingNotification(type: 'shop_new_booking')];
      final router = await pumpBookingTab(tester, bookings);
      await tester.tap(find.textContaining('新訂位：'));
      await tester.pumpAndSettle();
      expect(router.state.uri.path, '/booking/board');
    });

    testWidgets('點已讀的通知：不送出，直接前往', (tester) async {
      final bookings = FakeBookingRepository()
        ..notifications = [fakeBookingNotification(readAt: nowUtc)];
      final router = await pumpBookingTab(tester, bookings);
      await tester.tap(find.text('你在「甲店」的訂位已成功'));
      await tester.pumpAndSettle();
      expect(bookings.markReadCalls, isEmpty);
      expect(router.state.uri.path, '/booking/mine');
    });

    testWidgets('標成已讀失敗：仍然前往，回來後維持未讀', (tester) async {
      final bookings = bookingsUnread(1)..markReadError = failure;
      final router = await pumpBookingTab(tester, bookings);
      await tester.tap(find.text('你在「甲店」的訂位已成功'));
      await tester.pumpAndSettle();
      expect(router.state.uri.path, '/booking/mine');

      router.go('/notifications');
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('booking-notification-unread-bn-1')),
        findsOneWidget,
      );
    });

    testWidgets('沒有通知：「目前沒有訂位通知」', (tester) async {
      await pumpBookingTab(tester, FakeBookingRepository());
      expect(find.text('目前沒有訂位通知'), findsOneWidget);
    });

    testWidgets('載入失敗：中文錯誤與重試', (tester) async {
      final bookings = FakeBookingRepository()..notificationsError = failure;
      await pumpBookingTab(tester, bookings);
      expect(find.text('伺服器忙碌中'), findsOneWidget);
      expect(find.textContaining('SERVER_ERROR'), findsNothing);

      bookings
        ..notificationsError = null
        ..notifications = [fakeBookingNotification()];
      await tester.tap(find.text('重試'));
      await tester.pumpAndSettle();
      expect(find.text('你在「甲店」的訂位已成功'), findsOneWidget);
    });

    testWidgets('捲到底：載入下一頁', (tester) async {
      final bookings = FakeBookingRepository()
        ..notifications = [
          for (var i = 25; i >= 1; i--)
            fakeBookingNotification(id: 'bn-$i', shopName: '第 $i 店'),
        ];
      await pumpBookingTab(tester, bookings);
      expect(bookings.notificationCalls.where((c) => c.page == 2), isEmpty);
      await tester.scrollUntilVisible(
        find.text('你在「第 1 店」的訂位已成功'),
        300,
        scrollable: find
            .descendant(
              of: find.byKey(const Key('booking-notifications-list')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await tester.pumpAndSettle();
      expect(
        bookings.notificationCalls.where((c) => c.page == 2),
        hasLength(1),
      );
      expect(find.text('你在「第 1 店」的訂位已成功'), findsOneWidget);
    });
  });
}
