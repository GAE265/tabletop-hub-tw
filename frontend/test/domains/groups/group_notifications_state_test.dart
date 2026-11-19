// 揪團通知的 state（spec：add-groups-notifications 的 groups-notifications-page）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/state/group_notifications_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');

void main() {
  group('鈴鐺的未讀數', () {
    test('啟動時查詢一次，只查一筆', () async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          fakeNotification(id: 'n-1'),
          fakeNotification(id: 'n-2'),
          fakeNotification(id: 'n-3', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      container.read(groupUnreadCountProvider);
      await container.pump();
      await Future<void>.delayed(Duration.zero);
      expect(container.read(groupUnreadCountProvider), 2);
      expect(repo.notificationCalls.single.pageSize, 1);
    });

    test('查詢失敗：沒有數字（null），不丟出錯誤', () async {
      final repo = FakeGroupsRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      container.read(groupUnreadCountProvider);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(groupUnreadCountProvider), isNull);
    });

    test('鈴鐺文字：0 不顯示、超過 99 顯示 99+', () {
      expect(unreadBadgeLabel(null), isNull);
      expect(unreadBadgeLabel(0), isNull);
      expect(unreadBadgeLabel(3), '3');
      expect(unreadBadgeLabel(99), '99');
      expect(unreadBadgeLabel(120), '99+');
    });
  });

  group('通知列表', () {
    test('載入第一頁，並同步鈴鐺的未讀數', () async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          fakeNotification(id: 'n-2'),
          fakeNotification(id: 'n-1', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;
      final state = container.read(groupNotificationsProvider);
      expect(state.items.value!.map((n) => n.id), ['n-2', 'n-1']);
      expect(state.hasMore, isFalse);
      expect(container.read(groupUnreadCountProvider), 1);
    });

    test('載入失敗：錯誤，重試後成功', () async {
      final repo = FakeGroupsRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;
      expect(container.read(groupNotificationsProvider).items.hasError, isTrue);

      repo
        ..notificationsError = null
        ..notifications = [fakeNotification()];
      await notifier.reload();
      expect(
        container.read(groupNotificationsProvider).items.value,
        hasLength(1),
      );
    });

    test('下一頁：接在後面，載完後沒有下一頁', () async {
      final repo = FakeGroupsRepository()
        ..notifications = [
          for (var i = 25; i >= 1; i--) fakeNotification(id: 'n-$i'),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;
      expect(
        container.read(groupNotificationsProvider).items.value,
        hasLength(20),
      );
      expect(container.read(groupNotificationsProvider).hasMore, isTrue);

      await notifier.loadMore();
      final state = container.read(groupNotificationsProvider);
      expect(state.items.value, hasLength(25));
      expect(state.items.value!.last.id, 'n-1');
      expect(state.hasMore, isFalse);
      expect(repo.notificationCalls.last, (page: 2, pageSize: 20));
    });

    test('點未讀的通知：標成已讀，鈴鐺少 1', () async {
      final repo = FakeGroupsRepository()
        ..notifications = [fakeNotification(id: 'n-2'), fakeNotification()];
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;

      await notifier.open(repo.notifications.first);
      expect(repo.markReadCalls, ['n-2']);
      final items = container.read(groupNotificationsProvider).items.value!;
      expect(items.first.readAt, isNotNull);
      expect(items.last.readAt, isNull);
      expect(container.read(groupUnreadCountProvider), 1);
    });

    test('點已讀的通知：不送出', () async {
      final repo = FakeGroupsRepository()
        ..notifications = [fakeNotification(readAt: nowUtc)];
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;

      await notifier.open(repo.notifications.first);
      expect(repo.markReadCalls, isEmpty);
    });

    test('標成已讀失敗：維持未讀，鈴鐺數字不變', () async {
      final repo = FakeGroupsRepository()..notifications = [fakeNotification()];
      final container = makeContainer(repo);
      final notifier = container.read(groupNotificationsProvider.notifier);
      await notifier.loaded;
      repo.markReadError = failure;

      await notifier.open(repo.notifications.first);
      final items = container.read(groupNotificationsProvider).items.value!;
      expect(items.single.readAt, isNull);
      expect(container.read(groupUnreadCountProvider), 1);
    });
  });

  test('通知文字', () {
    expect(
      notificationText(fakeNotification(type: 'group_confirmed')),
      '「週末輕策略」已成團',
    );
    expect(
      notificationText(fakeNotification(type: 'group_cancelled')),
      '「週末輕策略」已取消',
    );
    expect(
      notificationText(fakeNotification(type: 'waitlist_promoted')),
      '你已從候補遞補為「週末輕策略」的成員',
    );
  });
}
