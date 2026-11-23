import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/notifications/notification_poll.dart';
import '../data/booking_notification.dart';
import '../data/booking_repository.dart';
import 'booking_overtime.dart';

/// 目前使用者的 id；換人時重新查詢通知。
final _currentUserIdProvider = Provider<String?>(
  (ref) => ref.watch(currentDevUserProvider)?.id,
);

const _taipeiOffset = Duration(hours: 8);
const _weekdays = ['一', '二', '三', '四', '五', '六', '日'];

String _two(int n) => n.toString().padLeft(2, '0');

DateTime _taipei(DateTime utc) => utc.toUtc().add(_taipeiOffset);

/// 台灣時間（通知依日期分段用）。
DateTime bookingTaipeiTime(DateTime utc) => _taipei(utc);

/// `11/22（日）`（台灣時間）
String bookingNotificationDate(DateTime utc) {
  final d = _taipei(utc);
  return '${d.month}/${d.day}（${_weekdays[d.weekday - 1]}）';
}

/// `19:00`（台灣時間）
String bookingNotificationClock(DateTime utc) {
  final d = _taipei(utc);
  return '${_two(d.hour)}:${_two(d.minute)}';
}

/// `11/14 11:05`（台灣時間），通知時間用。
String bookingNotificationShortDateTime(DateTime utc) {
  final d = _taipei(utc);
  return '${d.month}/${d.day} ${bookingNotificationClock(utc)}';
}

/// 一則訂位通知的說明（add-booking-notifications D2）。
String bookingNotificationText(BookingNotification n) => switch (n.type) {
  'shop_new_booking' =>
    '新訂位：${bookingNotificationDate(n.booking.startAt)}'
        '${bookingNotificationClock(n.booking.startAt)}・${n.booking.partySize} 人',
  _ => '你在「${n.booking.shopName}」的訂位已成功',
};

/// 點一則通知要前往的頁面：玩家去我的訂位，店家人員去店家看板。
String bookingNotificationRoute(BookingNotification n) =>
    n.type == 'shop_new_booking' ? '/booking/board' : '/booking/mine';

/// 目前使用者的訂位未讀數；查詢失敗時為 null（鈴鐺不算這邊、也不跳錯誤）。
///
/// 建立時查詢一次，之後每隔 [notificationPollIntervalProvider] 重新查詢；換人時重來。
class BookingUnreadCountNotifier extends Notifier<int?> {
  @override
  int? build() {
    ref.watch(_currentUserIdProvider);
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
          .read(bookingRepositoryProvider)
          .listNotifications(pageSize: 1);
      if (ref.mounted) state = page.unreadCount;
    } on Object {
      if (ref.mounted) state = null;
    }
  }

  /// 通知列表載入或標成已讀後，直接更新數字，不必等下一次查詢。
  void set(int? count) => state = count;
}

final bookingUnreadCountProvider =
    NotifierProvider<BookingUnreadCountNotifier, int?>(
      BookingUnreadCountNotifier.new,
    );

class BookingNotificationsState {
  const BookingNotificationsState({
    required this.items,
    this.total = 0,
    this.loadingMore = false,
  });

  final AsyncValue<List<BookingNotification>> items;
  final int total;

  /// 正在載入下一頁。
  final bool loadingMore;

  /// 還有沒載入的通知。
  bool get hasMore => (items.value?.length ?? 0) < total;

  BookingNotificationsState copyWith({
    AsyncValue<List<BookingNotification>>? items,
    int? total,
    bool? loadingMore,
  }) => BookingNotificationsState(
    items: items ?? this.items,
    total: total ?? this.total,
    loadingMore: loadingMore ?? this.loadingMore,
  );
}

/// 訂位通知列表：分頁載入、重試、點一則時標成已讀。
class BookingNotificationsNotifier extends Notifier<BookingNotificationsState> {
  static const pageSize = 20;

  Future<void> _pending = Future.value();

  /// 最近一次載入完成的 Future。
  Future<void> get loaded => _pending;

  BookingRepository get _repo => ref.read(bookingRepositoryProvider);

  @override
  BookingNotificationsState build() {
    ref.watch(_currentUserIdProvider);
    // 先啟動鈴鐺的未讀數，它的第一次查詢和列表一起進行
    ref.read(bookingUnreadCountProvider);
    _pending = Future.microtask(_fetchFirst);
    return const BookingNotificationsState(items: AsyncLoading());
  }

  Future<void> reload() {
    state = const BookingNotificationsState(items: AsyncLoading());
    return _pending = _fetchFirst();
  }

  Future<void> _fetchFirst() async {
    try {
      final page = await _repo.listNotifications(pageSize: pageSize);
      if (!ref.mounted) return;
      state = BookingNotificationsState(
        items: AsyncData(page.items),
        total: page.total,
      );
      ref.read(bookingUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object catch (error, stack) {
      if (!ref.mounted) return;
      state = BookingNotificationsState(items: AsyncError(error, stack));
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
      state = BookingNotificationsState(
        items: AsyncData([
          ...current,
          ...page.items.where((n) => !known.contains(n.id)),
        ]),
        total: page.total,
      );
      ref.read(bookingUnreadCountProvider.notifier).set(page.unreadCount);
    } on Object {
      if (ref.mounted) state = state.copyWith(loadingMore: false);
    }
  }

  /// 點一則通知：未讀的先在畫面上標成已讀、鈴鐺少 1，再送出；失敗時改回未讀。
  /// 不論成功與否，畫面之後都前往 [bookingNotificationRoute]。
  Future<void> open(BookingNotification notification) async {
    if (notification.readAt != null) return;
    final unread = ref.read(bookingUnreadCountProvider.notifier);
    final before = ref.read(bookingUnreadCountProvider);
    _replace(notification.copyWith(readAt: ref.read(bookingClockProvider)()));
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

  void _replace(BookingNotification notification) {
    final items = state.items.value;
    if (items == null) return;
    state = state.copyWith(
      items: AsyncData([
        for (final n in items) n.id == notification.id ? notification : n,
      ]),
    );
  }
}

final bookingNotificationsProvider =
    NotifierProvider.autoDispose<
      BookingNotificationsNotifier,
      BookingNotificationsState
    >(BookingNotificationsNotifier.new);
