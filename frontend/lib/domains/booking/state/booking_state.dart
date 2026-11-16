import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/booking.dart';
import '../data/booking_repository.dart';

/// 訂位畫面的狀態。[message] 顯示最近一次操作的結果或錯誤。
class BookingState {
  const BookingState({
    this.loading = false,
    this.message,
    this.isError = false,
    this.quote = const [],
    this.mine = const [],
    this.board = const [],
  });

  final bool loading;
  final String? message;
  final bool isError;
  final List<QuoteItem> quote;
  final List<Booking> mine;
  final List<Booking> board;

  BookingState copyWith({
    bool? loading,
    String? message,
    bool? isError,
    List<QuoteItem>? quote,
    List<Booking>? mine,
    List<Booking>? board,
  }) => BookingState(
    loading: loading ?? this.loading,
    message: message ?? this.message,
    isError: isError ?? this.isError,
    quote: quote ?? this.quote,
    mine: mine ?? this.mine,
    board: board ?? this.board,
  );
}

class BookingNotifier extends Notifier<BookingState> {
  BookingRepository get _repo => ref.read(bookingRepositoryProvider);

  @override
  BookingState build() => const BookingState();

  /// 執行一個操作：顯示載入中，成功時用 [onOk] 更新狀態，失敗時顯示錯誤。
  Future<void> _run(
    Future<BookingState Function(BookingState)> Function() action,
  ) async {
    state = state.copyWith(loading: true);
    try {
      final apply = await action();
      state = apply(state).copyWith(loading: false, isError: false);
    } on ApiException catch (e) {
      state = state.copyWith(
        loading: false,
        isError: true,
        message: '${e.code}：${e.message}',
      );
    }
  }

  Future<void> requestQuote(String shopId, int partySize, List<Slot> slots) =>
      _run(() async {
        final items = await _repo.quote(
          shopId: shopId,
          partySize: partySize,
          slots: slots,
        );
        return (s) => s.copyWith(quote: items, message: '預估完成');
      });

  Future<void> create(
    String shopId,
    int partySize,
    List<Slot> slots,
    String? specialRequests,
  ) => _run(() async {
    final items = await _repo.create(
      shopId: shopId,
      partySize: partySize,
      slots: slots,
      specialRequests: specialRequests,
    );
    final mine = await _repo.listMine();
    return (s) => s.copyWith(
      mine: mine.items,
      message: '已建立 ${items.length} 筆訂位',
    );
  });

  Future<void> loadMine() => _run(() async {
    final page = await _repo.listMine();
    return (s) => s.copyWith(mine: page.items, message: '我的訂位共 ${page.total} 筆');
  });

  Future<void> loadBoard(String shopId, String from, String to) =>
      _run(() async {
        final page = await _repo.listForShop(
          shopId: shopId,
          from: from,
          to: to,
        );
        return (s) => s.copyWith(
          board: page.items,
          message: '店員看板共 ${page.total} 筆',
        );
      });

  Future<void> refreshOne(int id) => _run(() async {
    final b = await _repo.get(id);
    return (s) => _replace(s, b, '查詢：${b.reservationCode} ${b.status}');
  });

  /// 修改時間與人數。
  Future<void> modify(int id, Slot slot, int partySize) => _run(() async {
    final b = await _repo.patch(id, {
      'start_at': slot.startAt,
      'end_at': slot.endAt,
      'party_size': partySize,
    });
    return (s) => _replace(s, b, '已修改${b.notice == null ? '' : '：${b.notice}'}');
  });

  /// 變更狀態：`cancelled`、`seated`、`completed`。
  Future<void> setStatus(int id, String status) => _run(() async {
    final b = await _repo.patch(id, {'status': status});
    return (s) => _replace(
      s,
      b,
      '狀態已改為 ${b.status}${b.finalFee == null ? '' : '，結算 ${b.finalFee}'}',
    );
  });

  BookingState _replace(BookingState s, Booking b, String message) {
    List<Booking> swap(List<Booking> list) => [
      for (final x in list) x.id == b.id ? b : x,
    ];
    return s.copyWith(
      mine: swap(s.mine),
      board: swap(s.board),
      message: message,
    );
  }
}

final bookingProvider = NotifierProvider<BookingNotifier, BookingState>(
  BookingNotifier.new,
);
