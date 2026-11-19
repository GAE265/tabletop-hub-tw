// 通知鈴鐺與通知列表頁（spec：add-groups-notifications 的 groups-notifications-page）。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/pages/group_notifications_page.dart';
import 'package:tabletop_hub/domains/groups/pages/widgets/notification_bell.dart';
import 'package:tabletop_hub/domains/groups/state/current_user.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');

/// 首頁放鈴鐺，`/groups/notifications` 是通知列表頁。
Future<GoRouter> pumpWithRouter(
  WidgetTester tester,
  FakeGroupsRepository repo, {
  String location = '/',
}) async {
  setScreenSize(tester, const Size(400, 900));
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
        path: '/groups/notifications',
        builder: (context, state) => const GroupNotificationsPage(),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        groupsRepositoryProvider.overrideWithValue(repo),
        groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
        currentUserIdProvider.overrideWithValue('u-player'),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  return router;
}

FakeGroupsRepository repoWithUnread(int count) => FakeGroupsRepository()
  ..notifications = [
    for (var i = count; i >= 1; i--) fakeNotification(id: 'n-$i'),
  ];

Finder badgeText(String text) => find.descendant(
  of: find.byKey(const Key('bell')),
  matching: find.text(text),
);

void main() {
  group('通知鈴鐺', () {
    testWidgets('有未讀：顯示數字', (tester) async {
      await pumpWithRouter(tester, repoWithUnread(3));
      expect(badgeText('3'), findsOneWidget);
    });

    testWidgets('超過 99：顯示 99+', (tester) async {
      await pumpWithRouter(tester, repoWithUnread(120));
      expect(badgeText('99+'), findsOneWidget);
    });

    testWidgets('沒有未讀：不顯示數字', (tester) async {
      await pumpWithRouter(tester, repoWithUnread(0));
      expect(find.byKey(const Key('bell')), findsOneWidget);
      expect(find.byKey(const Key('notification-bell-count')), findsNothing);
    });

    testWidgets('查詢失敗：鈴鐺照常顯示、沒有數字、不跳錯誤', (tester) async {
      final repo = FakeGroupsRepository()..notificationsError = failure;
      await pumpWithRouter(tester, repo);
      expect(find.byKey(const Key('bell')), findsOneWidget);
      expect(find.byKey(const Key('notification-bell-count')), findsNothing);
      expect(find.text('伺服器忙碌中'), findsNothing);
    });

    testWidgets('每 60 秒重新查詢', (tester) async {
      final repo = repoWithUnread(1);
      await pumpWithRouter(tester, repo);
      expect(badgeText('1'), findsOneWidget);

      repo.notifications = [fakeNotification(id: 'n-2'), ...repo.notifications];
      await tester.pump(const Duration(seconds: 59));
      expect(badgeText('1'), findsOneWidget);
      await tester.pump(const Duration(seconds: 1));
      await tester.pump();
      expect(badgeText('2'), findsOneWidget);
    });

    testWidgets('點鈴鐺：前往通知列表頁', (tester) async {
      final router = await pumpWithRouter(tester, repoWithUnread(1));
      await tester.tap(find.byKey(const Key('bell')));
      await tester.pumpAndSettle();
      expect(router.state.uri.path, '/groups/notifications');
      expect(find.byKey(const Key('group-notifications-page')), findsOneWidget);
    });
  });

  group('通知列表頁', () {
    Future<void> pumpPage(WidgetTester tester, FakeGroupsRepository repo) =>
        pumpGroupsWidget(tester, const GroupNotificationsPage(), repo: repo);

    testWidgets('三種通知的文字、揪團時間與通知時間', (tester) async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          fakeNotification(
            id: 'n-3',
            type: 'waitlist_promoted',
            groupTitle: '阿瓦隆夜',
            groupStartAt: taipei(11, 21, 19),
            createdAt: taipei(11, 14, 11, 5),
          ),
          fakeNotification(
            id: 'n-2',
            type: 'group_cancelled',
            groupTitle: '卡坦島',
          ),
          fakeNotification(id: 'n-1', type: 'group_confirmed', readAt: nowUtc),
        ];
      await pumpPage(tester, repo);
      final texts = ['你已從候補遞補為「阿瓦隆夜」的成員', '「卡坦島」已取消', '「週末輕策略」已成團'];
      for (final text in texts) {
        expect(find.text(text), findsOneWidget);
      }
      // 新的在前
      expect(
        tester.getTopLeft(find.text(texts[0])).dy,
        lessThan(tester.getTopLeft(find.text(texts[1])).dy),
      );
      expect(find.textContaining('揪團時間 2026/11/21（六） 19:00'), findsOneWidget);
      expect(find.textContaining('通知時間 11/14 11:05'), findsOneWidget);
    });

    testWidgets('未讀與已讀看得出差別', (tester) async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          fakeNotification(id: 'n-2'),
          fakeNotification(id: 'n-1', readAt: nowUtc),
        ];
      await pumpPage(tester, repo);
      expect(find.byKey(const Key('notification-unread-n-2')), findsOneWidget);
      expect(find.byKey(const Key('notification-unread-n-1')), findsNothing);
    });

    testWidgets('點未讀的通知：標成已讀並前往揪團詳細頁', (tester) async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 21))],
      )..notifications = [fakeNotification(id: 'n-1', groupId: 'g-1')];
      await pumpPage(tester, repo);
      await tester.tap(find.text('「週末輕策略」已成團'));
      await tester.pumpAndSettle();
      expect(repo.markReadCalls, ['n-1']);
      expect(find.byKey(const Key('group-detail-page')), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('notification-unread-n-1')), findsNothing);
    });

    testWidgets('點已讀的通知：不送出，直接前往詳細頁', (tester) async {
      final repo = FakeGroupsRepository(
        groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 21))],
      )..notifications = [fakeNotification(id: 'n-1', readAt: nowUtc)];
      await pumpPage(tester, repo);
      await tester.tap(find.text('「週末輕策略」已成團'));
      await tester.pumpAndSettle();
      expect(repo.markReadCalls, isEmpty);
      expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    });

    testWidgets('標成已讀失敗：仍然前往詳細頁，維持未讀', (tester) async {
      final repo =
          FakeGroupsRepository(
              groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 21))],
            )
            ..notifications = [fakeNotification(id: 'n-1')]
            ..markReadError = failure;
      await pumpPage(tester, repo);
      await tester.tap(find.text('「週末輕策略」已成團'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group-detail-page')), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('notification-unread-n-1')), findsOneWidget);
    });

    testWidgets('載入中', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupNotificationsPage(),
        repo: FakeGroupsRepository(),
        settle: false,
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('沒有通知：「目前沒有通知」', (tester) async {
      await pumpPage(tester, FakeGroupsRepository());
      expect(find.text('目前沒有通知'), findsOneWidget);
    });

    testWidgets('載入失敗：中文錯誤與重試', (tester) async {
      final repo = FakeGroupsRepository()..notificationsError = failure;
      await pumpPage(tester, repo);
      expect(find.text('伺服器忙碌中'), findsOneWidget);
      expect(find.textContaining('SERVER_ERROR'), findsNothing);

      repo
        ..notificationsError = null
        ..notifications = [fakeNotification()];
      await tester.tap(find.text('重試'));
      await tester.pumpAndSettle();
      expect(find.text('「週末輕策略」已成團'), findsOneWidget);
    });

    testWidgets('捲到底：載入下一頁', (tester) async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          for (var i = 25; i >= 1; i--)
            fakeNotification(id: 'n-$i', groupTitle: '第 $i 團'),
        ];
      await pumpPage(tester, repo);
      expect(repo.notificationCalls.where((c) => c.page == 2), isEmpty);
      await tester.scrollUntilVisible(
        find.text('「第 1 團」已成團'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(repo.notificationCalls.where((c) => c.page == 2), hasLength(1));
      expect(find.text('「第 1 團」已成團'), findsOneWidget);
    });
  });
}
