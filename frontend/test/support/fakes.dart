import 'package:dio/dio.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/data/shop.dart';
import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';

const fakePlayer = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');
const fakeStaff = DevUser(
  id: 'u-staff',
  displayName: '測試店家人員',
  role: 'shop_staff',
  shopId: 's-shop',
);
const fakeAdmin = DevUser(id: 'u-admin', displayName: '測試管理員', role: 'admin');

class FakeDevUsersRepository implements DevUsersRepository {
  FakeDevUsersRepository({
    this.users = const [fakePlayer, fakeStaff, fakeAdmin],
    this.error,
  });

  List<DevUser> users;
  Object? error;
  int callCount = 0;

  @override
  Future<List<DevUser>> list() async {
    callCount++;
    if (error != null) throw error!;
    return users;
  }
}

class FakeHealthRepository implements HealthRepository {
  FakeHealthRepository({this.result, this.error});

  HealthStatus? result;
  Object? error;

  @override
  Future<HealthStatus> fetch() async {
    if (error != null) throw error!;
    return result!;
  }
}

/// 記錄請求並回傳固定 JSON 的 Dio adapter，用來檢查請求標頭。
class RecordingAdapter implements HttpClientAdapter {
  final requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return ResponseBody.fromString(
      '{}',
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// 手寫的 booking repository 假實作（AGENTS.md 7.5，不使用 mock 套件）。
class FakeBookingRepository implements BookingRepository {
  FakeBookingRepository({
    this.shops = const [fakeShopA, fakeShopB],
    this.shopError,
    this.mine = const [],
    this.board = const [],
  });

  List<Shop> shops;
  Object? shopError;
  List<Booking> mine;
  List<Booking> board;
  int shopCallCount = 0;

  @override
  Future<List<Shop>> listShops() async {
    shopCallCount++;
    if (shopError != null) throw shopError!;
    return shops;
  }

  @override
  Future<QuoteResult> quote({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
  }) async => QuoteResult(
    startAt: startAt,
    endAt: endAt,
    fee: const Fee(billableHours: '2.00', venueFee: '480.00'),
    tableCodes: ['T1'],
  );

  @override
  Future<Booking> create({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
    String? specialRequests,
    bool confirmOverlap = false,
  }) async => Booking(
    id: 1,
    reservationCode: 'BKFAKE',
    shopId: shopId,
    startAt: startAt,
    endAt: endAt,
    partySize: partySize,
    status: 'confirmed',
    tableCodes: ['T1'],
    estimatedFee: const Fee(billableHours: '2.00', venueFee: '480.00'),
  );

  @override
  Future<Booking> get(int id) => throw UnimplementedError();

  @override
  Future<Booking> patch(int id, Map<String, dynamic> patch) =>
      throw UnimplementedError();

  @override
  Future<BookingPage> listMine({String? status, String? fromDate, String? toDate}) async =>
      BookingPage(items: mine, total: mine.length);

  @override
  Future<BookingPage> listForShop({
    required String shopId,
    required String from,
    required String to,
  }) async => BookingPage(items: board, total: board.length);
}

const fakeShopA = Shop(id: 's-a', name: '甲店');
const fakeShopB = Shop(id: 's-b', name: '乙店');
