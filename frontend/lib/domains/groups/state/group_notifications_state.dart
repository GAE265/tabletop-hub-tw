import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/notifications/notification_poll.dart';
import '../data/group_notification.dart';
import '../data/groups_repository.dart';
import 'current_user.dart';
import 'group_clock.dart';

export '../../../core/notifications/notification_poll.dart';
export 'group_labels.dart' show notificationText;

/// 目前使用者的未讀通知數；查詢失敗時為 null（鈴鐺不顯示數字，也不跳錯誤）。
///
/// 建立時查詢一次，之後每隔 [notificationPollIntervalProvider] 重新查詢；換人時重來。
class GroupUnreadCountNotifier extends Notifier<int?> {
  @override
  int? build() {
    ref.watch(currentUserIdProvider);
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
          .read(groupsRepositoryProvider)
          .listNotifications(pageSize: 1);
      if (ref.mounted) state = page.unreadCount;
    } on Object {
      if (ref.mounted) state = null;
    }
  }

  /// 通知列表載入或標成已讀後，直接更新數字，不必等下一次查詢。
  void set(int? count) => state = count;
}

final groupUnreadCountProvider =
    NotifierProvider<GroupUnreadCountNotifier, int?>(
      GroupUnreadCountNotifier.new,
    );

class GroupNotificationsState {
  const GroupNotificationsState({
    required this.items,
    this.total = 0,
    this.loadingMore = false,
  });

  final AsyncValue<List<GroupNotification>> items;
  final int total;

  /// 正在載入下一頁。
  final bool loadingMore;

  /// 還有沒載入的通知。
  bool get hasMore => (items.value?.length ?? 0) < total;

  GroupNotificationsState copyWith({
    AsyncValue<List<GroupNotification>>? items,
    int? total,
    bool? loadingMore,
  }) => GroupNotificationsState(
    items: items ?? this.items,
    total: total ?? this.total,
    loadingMore: loadingMore ?? this.loadingMore,
  );
}

/// 通知列表頁：分頁載入、重試、點一則時標成已讀。
class GroupNotificationsNotifier extends Notifier<GroupNotificationsState> {
  static const pageSize = 20;

  Future<void> _pending = Future.value();

  /// 最近一次載入完成的 Future。
  Future<void> get loaded => _pending;

  GroupsRepository get _repo => ref.read(groupsRepositoryProvider);

  @override
  GroupNotificationsState build() {
    ref.watch(currentUserIdProvider);
    // 先啟動鈴鐺的未讀數，它的第一次查詢和列表一起進行
    ref.read(groupUnreadCountProvider);
    _pending = Future.microtask(_fetchFirst);
    return const GroupNotificationsState(items: AsyncLoading());
  }

  Future<void> reload() {
    state = const GroupNotificationsState(items: AsyncLoading());
    return _pending = _fetchFirst();
  }

  Future<void> _fetchFirst() async {
    try {
      final page = await _repo.listNotifications(pageSize: pageSize);
      if (!ref.mounted) return;
      state = GroupNotificationsState(
        items: AsyncData(page.items),
        total: page.total,
      );
      ref.read(groupUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object catch (error, stack) {
      if (!ref.mounted) return;
      state = GroupNotificationsState(items: AsyncError(error, stack));
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
      state = GroupNotificationsState(
        items: AsyncData([
          ...current,
          ...page.items.where((n) => !known.contains(n.id)),
        ]),
        total: page.total,
      );
      ref.read(groupUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object {
      if (ref.mounted) state = state.copyWith(loadingMore: false);
    }
  }

  /// 點一則通知：未讀的先在畫面上標成已讀、鈴鐺少 1，再送出；失敗時改回未讀。
  /// 不論成功與否，畫面之後都前往該揪團。
  Future<void> open(GroupNotification notification) async {
    if (notification.readAt != null) return;
    final unread = ref.read(groupUnreadCountProvider.notifier);
    final before = ref.read(groupUnreadCountProvider);
    _replace(notification.copyWith(readAt: ref.read(groupClockProvider).now()));
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

  void _replace(GroupNotification notification) {
    final items = state.items.value;
    if (items == null) return;
    state = state.copyWith(
      items: AsyncData([
        for (final n in items) n.id == notification.id ? notification : n,
      ]),
    );
  }
}

final groupNotificationsProvider =
    NotifierProvider.autoDispose<
      GroupNotificationsNotifier,
      GroupNotificationsState
    >(GroupNotificationsNotifier.new);
