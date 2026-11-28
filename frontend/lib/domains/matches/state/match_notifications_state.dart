import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/notifications/notification_poll.dart';
import '../data/match_notification.dart';
import '../data/matches_repository.dart';
import 'match_current_user.dart';

export '../../../core/notifications/notification_poll.dart';

/// 現在時間（UTC）；測試換成固定時間，通知依日期分段用。
final matchNotificationsClockProvider = Provider<DateTime Function()>(
  (ref) => DateTime.now,
);

const _taipeiOffset = Duration(hours: 8);

String _two(int n) => n.toString().padLeft(2, '0');

/// 台灣時間（通知依日期分段用）。
DateTime matchTaipeiTime(DateTime utc) => utc.toUtc().add(_taipeiOffset);

/// `11/20 11:05`（台灣時間），通知時間用。
String matchNotificationShortDateTime(DateTime utc) {
  final d = matchTaipeiTime(utc);
  return '${d.month}/${d.day} ${_two(d.hour)}:${_two(d.minute)}';
}

/// 一則戰績通知的說明，包含記錄者的名稱。文字由前端依種類組成，後端不存。
String matchNotificationText(MatchNotification n) {
  final game = '《${n.match.gameName}》';
  return switch (n.type) {
    'match_result_recorded' => '${n.recordedBy.displayName} 記錄了$game的結果，請確認',
    _ => '$game有新的消息',
  };
}

/// 點一則通知要前往的頁面：那一局的紀錄頁。
String matchNotificationRoute(MatchNotification n) => '/matches/${n.match.id}';

/// 目前使用者的戰績未讀數；查詢失敗時為 null（鈴鐺不算這邊、也不跳錯誤）。
///
/// 建立時查詢一次，之後每隔 [notificationPollIntervalProvider] 重新查詢；換人時重來。
class MatchUnreadCountNotifier extends Notifier<int?> {
  @override
  int? build() {
    ref.watch(matchUserIdProvider);
    final timer = Timer.periodic(
      ref.watch(notificationPollIntervalProvider),
      (_) => refresh(),
    );
    ref.onDispose(timer.cancel);
    Future.microtask(refresh);
    return null;
  }

  Future<void> refresh() async {
    try {
      final page = await ref
          .read(matchesRepositoryProvider)
          .listNotifications(pageSize: 1);
      if (ref.mounted) state = page.unreadCount;
    } on Object {
      if (ref.mounted) state = null;
    }
  }

  /// 通知列表載入或標成已讀後，直接更新數字，不必等下一次查詢。
  void set(int? count) => state = count;
}

final matchUnreadCountProvider =
    NotifierProvider<MatchUnreadCountNotifier, int?>(
      MatchUnreadCountNotifier.new,
    );

class MatchNotificationsState {
  const MatchNotificationsState({
    required this.items,
    this.total = 0,
    this.loadingMore = false,
  });

  final AsyncValue<List<MatchNotification>> items;
  final int total;

  /// 正在載入下一頁。
  final bool loadingMore;

  /// 還有沒載入的通知。
  bool get hasMore => (items.value?.length ?? 0) < total;

  MatchNotificationsState copyWith({
    AsyncValue<List<MatchNotification>>? items,
    int? total,
    bool? loadingMore,
  }) => MatchNotificationsState(
    items: items ?? this.items,
    total: total ?? this.total,
    loadingMore: loadingMore ?? this.loadingMore,
  );
}

/// 戰績通知列表：分頁載入、重試、點一則時標成已讀。
class MatchNotificationsNotifier extends Notifier<MatchNotificationsState> {
  static const pageSize = 20;

  Future<void> _pending = Future.value();

  /// 最近一次載入完成的 Future。
  Future<void> get loaded => _pending;

  MatchesRepository get _repo => ref.read(matchesRepositoryProvider);

  @override
  MatchNotificationsState build() {
    ref.watch(matchUserIdProvider);
    // 先啟動鈴鐺的未讀數，它的第一次查詢和列表一起進行
    ref.read(matchUnreadCountProvider);
    _pending = Future.microtask(_fetchFirst);
    return const MatchNotificationsState(items: AsyncLoading());
  }

  Future<void> reload() {
    state = const MatchNotificationsState(items: AsyncLoading());
    return _pending = _fetchFirst();
  }

  Future<void> _fetchFirst() async {
    try {
      final page = await _repo.listNotifications(pageSize: pageSize);
      if (!ref.mounted) return;
      state = MatchNotificationsState(
        items: AsyncData(page.items),
        total: page.total,
      );
      ref.read(matchUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object catch (error, stack) {
      if (!ref.mounted) return;
      state = MatchNotificationsState(items: AsyncError(error, stack));
    }
  }

  /// 載入下一頁並接在後面。失敗時保留已載入的通知，之後捲動會再試。
  Future<void> loadMore() async {
    final current = state.items.value;
    if (current == null || state.loadingMore || !state.hasMore) return;
    state = state.copyWith(loadingMore: true);
    try {
      final page = await _repo.listNotifications(
        page: current.length ~/ pageSize + 1,
        pageSize: pageSize,
      );
      if (!ref.mounted) return;
      final known = {for (final n in current) n.id};
      state = MatchNotificationsState(
        items: AsyncData([
          ...current,
          ...page.items.where((n) => !known.contains(n.id)),
        ]),
        total: page.total,
      );
      ref.read(matchUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object {
      if (ref.mounted) state = state.copyWith(loadingMore: false);
    }
  }

  /// 點一則通知：未讀的先在畫面上標成已讀、鈴鐺少 1，再送出；失敗時改回未讀。
  /// 不論成功與否，畫面之後都前往 [matchNotificationRoute]。
  Future<void> open(MatchNotification notification) async {
    if (notification.readAt != null) return;
    final unread = ref.read(matchUnreadCountProvider.notifier);
    final before = ref.read(matchUnreadCountProvider);
    _replace(
      notification.copyWith(
        readAt: ref.read(matchNotificationsClockProvider)(),
      ),
    );
    if (before != null && before > 0) unread.set(before - 1);
    try {
      final read = await _repo.markNotificationRead(notification.id);
      if (ref.mounted) _replace(read);
    } on Object {
      if (!ref.mounted) return;
      _replace(notification);
      unread.set(before);
    }
  }

  void _replace(MatchNotification notification) {
    final items = state.items.value;
    if (items == null) return;
    state = state.copyWith(
      items: AsyncData([
        for (final n in items) n.id == notification.id ? notification : n,
      ]),
    );
  }
}

final matchNotificationsProvider =
    NotifierProvider.autoDispose<
      MatchNotificationsNotifier,
      MatchNotificationsState
    >(MatchNotificationsNotifier.new);
