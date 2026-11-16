import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import 'booking.dart';

abstract interface class BookingRepository {
  Future<List<QuoteItem>> quote({
    required String shopId,
    required int partySize,
    required List<Slot> slots,
  });

  Future<List<Booking>> create({
    required String shopId,
    required int partySize,
    required List<Slot> slots,
    String? specialRequests,
  });

  Future<Booking> get(int id);

  /// 修改時間／人數（[patch] 內放要改的欄位）或變更狀態（`{'status': ...}`）。
  Future<Booking> patch(int id, Map<String, dynamic> patch);

  Future<BookingPage> listMine();

  Future<BookingPage> listForShop({
    required String shopId,
    required String from,
    required String to,
  });
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
    List<Slot> slots,
  ) => {
    'shop_id': shopId,
    'party_size': partySize,
    'slots': [for (final s in slots) s.toJson()],
  };

  @override
  Future<List<QuoteItem>> quote({
    required String shopId,
    required int partySize,
    required List<Slot> slots,
  }) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/booking-quotes',
      data: _body(shopId, partySize, slots),
    );
    return [
      for (final i in r.data!['items'] as List)
        QuoteItem.fromJson(i as Map<String, dynamic>),
    ];
  });

  @override
  Future<List<Booking>> create({
    required String shopId,
    required int partySize,
    required List<Slot> slots,
    String? specialRequests,
  }) => _call(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/api/v1/bookings',
      data: {
        ..._body(shopId, partySize, slots),
        if (specialRequests != null && specialRequests.isNotEmpty)
          'special_requests': specialRequests,
      },
    );
    return BookingPage.fromJson(r.data!).items;
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
  Future<BookingPage> listMine() => _call(() async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/api/v1/bookings',
      queryParameters: {'page': 1, 'page_size': 50},
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
}

final bookingRepositoryProvider = Provider<BookingRepository>(
  (ref) => HttpBookingRepository(ref.watch(dioProvider)),
);
