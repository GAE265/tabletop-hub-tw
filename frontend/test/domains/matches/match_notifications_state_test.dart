// 戰績通知的 state：鈴鐺的未讀數、列表的載入與分頁、點一則時標成已讀
// （docs/mr_info/feature-matches-notifications.md 的前端情境表）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/matches/state/match_current_user.dart';
import 'package:tabletop_hub/domains/matches/state/match_notifications_state.dart';

import '../../support/fakes.dart';

const failure = ApiException(code: 'SERVER_ERROR', message: '伺服器忙碌中');

/// 台灣時間 11/20 12:00。
final nowUtc = DateTime.utc(2026, 11, 20, 4);

ProviderContainer makeContainer(FakeMatchesRepository repo) {
  final container = ProviderContainer(
    overrides: [
      matchesRepositoryProvider.overrideWithValue(repo),
      matchUserIdProvider.overrideWithValue('u-b'),
      matchNotificationsClockProvider.overrideWithValue(() => nowUtc),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('鈴鐺的戰績未讀數', () {
    test('啟動時查詢一次，只查一筆', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [
          fakeMatchNotification(id: 'mn-2'),
          fakeMatchNotification(id: 'mn-1', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      container.read(matchUnreadCountProvider);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(matchUnreadCountProvider), 1);
      expect(repo.notificationCalls.single.pageSize, 1);
    });

    test('查詢失敗：沒有數字（null），不丟出錯誤', () async {
      final repo = FakeMatchesRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      container.read(matchUnreadCountProvider);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(matchUnreadCountProvider), isNull);
    });
  });

  group('戰績通知列表', () {
    test('載入第一頁，並更新鈴鐺的未讀數', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [
          fakeMatchNotification(id: 'mn-2'),
          fakeMatchNotification(id: 'mn-1', readAt: nowUtc),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(matchNotificationsProvider.notifier);
      await notifier.loaded;
      final state = container.read(matchNotificationsProvider);
      expect(state.items.value!.map((n) => n.id), ['mn-2', 'mn-1']);
      expect(state.hasMore, isFalse);
      expect(container.read(matchUnreadCountProvider), 1);
    });

    test('載入失敗後重新載入', () async {
      final repo = FakeMatchesRepository()..notificationsError = failure;
      final container = makeContainer(repo);
      final notifier = container.read(matchNotificationsProvider.notifier);
      await notifier.loaded;
      expect(container.read(matchNotificationsProvider).items.hasError, isTrue);
      repo.notificationsError = null;
      repo.notifications = [fakeMatchNotification()];
      await notifier.reload();
      expect(
        container.read(matchNotificationsProvider).items.value,
        hasLength(1),
      );
    });

    test('下一頁：接在後面', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [
          for (var i = 25; i >= 1; i--) fakeMatchNotification(id: 'mn-$i'),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(matchNotificationsProvider.notifier);
      await notifier.loaded;
      expect(
        container.read(matchNotificationsProvider).items.value,
        hasLength(20),
      );
      expect(container.read(matchNotificationsProvider).hasMore, isTrue);
      await notifier.loadMore();
      final state = container.read(matchNotificationsProvider);
      expect(state.items.value, hasLength(25));
      expect(state.items.value!.last.id, 'mn-1');
      expect(state.hasMore, isFalse);
      expect(repo.notificationCalls.last, (page: 2, pageSize: 20));
    });
  });

  group('點一則通知', () {
    Future<(ProviderContainer, MatchNotificationsNotifier)> loaded(
      FakeMatchesRepository repo,
    ) async {
      final container = makeContainer(repo);
      final notifier = container.read(matchNotificationsProvider.notifier);
      await notifier.loaded;
      return (container, notifier);
    }

    test('未讀：標成已讀、鈴鐺少 1', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [fakeMatchNotification(id: 'mn-1')];
      final (container, notifier) = await loaded(repo);
      await notifier.open(repo.notifications.single);
      expect(repo.markReadCalls, ['mn-1']);
      expect(
        container.read(matchNotificationsProvider).items.value!.single.readAt,
        isNotNull,
      );
      expect(container.read(matchUnreadCountProvider), 0);
    });

    test('已讀：不送出', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [fakeMatchNotification(readAt: nowUtc)];
      final (_, notifier) = await loaded(repo);
      await notifier.open(repo.notifications.single);
      expect(repo.markReadCalls, isEmpty);
    });

    test('標成已讀失敗：改回未讀，鈴鐺數字還原', () async {
      final repo = FakeMatchesRepository()
        ..notifications = [fakeMatchNotification(id: 'mn-1')]
        ..markReadError = failure;
      final (container, notifier) = await loaded(repo);
      await notifier.open(repo.notifications.single);
      expect(
        container.read(matchNotificationsProvider).items.value!.single.readAt,
        isNull,
      );
      expect(container.read(matchUnreadCountProvider), 1);
    });
  });
}
