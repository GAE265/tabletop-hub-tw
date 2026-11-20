import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'booking.dart';
import 'booking_notification.dart';
import 'shop.dart';

abstract interface class BookingRepository {
  /// 列出所有啟用中的店家，供店家下拉選單使用。
  Future<List<Shop>> listShops();

  Future<QuoteResult> quote({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
  });

  Future<Booking> create({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
    String? specialRequests,
    bool confirmOverlap = false,
  });

  Future<Booking> get(int id);

  /// 修改時間／人數（[patch] 內放要改的欄位）或變更狀態（`{'status': ...}`）。
  Future<Booking> patch(int id, Map<String, dynamic> patch);

  Future<BookingPage> listMine({
    String? status,
    String? fromDate,
    String? toDate,
  });

  Future<BookingPage> listForShop({
    required String shopId,
    required String from,
    required String to,
  });

  Future<List<SeatingPlan>> getTablesStatus({
    required String shopId,
    String? from,
    String? to,
    int? floor,
  });

  /// 目前使用者的訂位通知，新的在前（add-booking-notifications）。
  Future<BookingNotificationPage> listNotifications({
    int page = 1,
    int pageSize = 20,
  });

  /// 把自己的一則通知標成已讀。
  Future<BookingNotification> markNotificationRead(String id);
}

class HttpBookingRepository implements BookingRepository {
  const HttpBookingRepository(this._dio);

  final Dio _dio;

  Future<T> _call<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Map<String, dynamic> _body(
    String shopId,
    int partySize,
    String startAt,
    String endAt, {
    String? specialRequests,
    bool confirmOverlap = false,
  }) => {
    'shop_id': shopId,
    'party_size': partySize,
    'start_at': startAt,
    'end_at': endAt,
    if (specialRequests != null && specialRequests.isNotEmpty)
      'special_requests': specialRequests,
    if (confirmOverlap) 'confirm_overlap': true,
  };

  @override
  Future<List<Shop>> listShops() => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>('/api/v1/shops');
    return ShopPage.fromJson(r.data!).items;
  });

  @override
  Future<QuoteResult> quote({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
  }) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/booking-quotes',
      data: _body(shopId, partySize, startAt, endAt),
    );
    return QuoteResult.fromJson(r.data!);
  });

  @override
  Future<Booking> create({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
    String? specialRequests,
    bool confirmOverlap = false,
  }) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/bookings',
      data: _body(shopId, partySize, startAt, endAt,
          specialRequests: specialRequests, confirmOverlap: confirmOverlap),
    );
    return Booking.fromJson(r.data!);
  });

  @override
  Future<Booking> get(int id) => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>('/api/v1/bookings/$id');
    return Booking.fromJson(r.data!);
  });

  @override
  Future<Booking> patch(int id, Map<String, dynamic> patch) => _call(() async {
    final r = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/bookings/$id',
      data: patch,
    );
    return Booking.fromJson(r.data!);
  });

  @override
  Future<BookingPage> listMine({
    String? status,
    String? fromDate,
    String? toDate,
  }) => _call(() async {
    final params = <String, dynamic>{'page': 1, 'page_size': 50};
    if (status != null && status.isNotEmpty) params['status'] = status;
    if (fromDate != null && fromDate.isNotEmpty) params['from'] = fromDate;
    if (toDate != null && toDate.isNotEmpty) params['to'] = toDate;
    final r = await _dio.get<Map<String, dynamic>>(
      '/api/v1/bookings',
      queryParameters: params,
    );
    return BookingPage.fromJson(r.data!);
  });

  @override
  Future<BookingPage> listForShop({
    required String shopId,
    required String from,
    required String to,
  }) => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/api/v1/shops/$shopId/bookings',
      queryParameters: {'from': from, 'to': to, 'page': 1, 'page_size': 100},
    );
    return BookingPage.fromJson(r.data!);
  });

  @override
  Future<List<SeatingPlan>> getTablesStatus({
    required String shopId,
    String? from,
    String? to,
    int? floor,
  }) => _call(() async {
    final params = <String, dynamic>{};
    if (from != null && from.isNotEmpty) params['from'] = from;
    if (to != null && to.isNotEmpty) params['to'] = to;
    if (floor != null) params['floor'] = floor;
    final r = await _dio.get<List>(
      '/api/v1/shops/$shopId/tables/status',
      queryParameters: params,
    );
    return [
      for (final item in r.data!)
        SeatingPlan.fromJson(item as Map<String, dynamic>),
    ];
  });

  @override
  Future<BookingNotificationPage> listNotifications({
    int page = 1,
    int pageSize = 20,
  }) => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/api/v1/booking-notifications',
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    return BookingNotificationPage.fromJson(r.data!);
  });

  @override
  Future<BookingNotification> markNotificationRead(String id) =>
      _call(() async {
        final r = await _dio.patch<Map<String, dynamic>>(
          '/api/v1/booking-notifications/$id',
          data: {'read': true},
        );
        return BookingNotification.fromJson(r.data!);
      });
}

final bookingRepositoryProvider = Provider<BookingRepository>(
  (ref) => HttpBookingRepository(ref.watch(dioProvider)),
);
