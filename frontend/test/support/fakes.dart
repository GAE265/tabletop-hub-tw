import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:tabletop_hub/app/theme/app_fonts.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/data/shop.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/data/group_input.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';

/// 測試用字型：只換字型名稱，不連網路下載。
class FakeAppFonts implements AppFonts {
  const FakeAppFonts();

  static const headingFamily = 'FakeHeading';
  static const bodyFamily = 'FakeBody';

  @override
  TextStyle heading(TextStyle style) =>
      style.copyWith(fontFamily: headingFamily);

  @override
  TextStyle body(TextStyle style) => style.copyWith(fontFamily: bodyFamily);
}

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

  /// 設定後，清單要等它完成才回應（模擬真的網路比畫面晚到）。
  Completer<void>? gate;

  @override
  Future<List<DevUser>> list() async {
    callCount++;
    if (gate != null) await gate!.future;
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

/// 每次送出都停在「等待回應」，由測試呼叫 [respond] 或 [fail] 決定結果，
/// 才看得到送出中的狀態。
class FakeAdvisorRepository implements AdvisorRepository {
  final requests = <AdvisorMessageRequest>[];
  final _pending = <Completer<AdvisorMessageResponse>>[];

  @override
  Future<AdvisorMessageResponse> sendMessage(AdvisorMessageRequest request) {
    requests.add(request);
    final completer = Completer<AdvisorMessageResponse>();
    _pending.add(completer);
    return completer.future;
  }

  /// 最早那個還在等的請求收到回應。
  void respond(AdvisorMessageResponse response) =>
      _pending.removeAt(0).complete(response);

  /// 最早那個還在等的請求失敗。
  void fail(Object error) => _pending.removeAt(0).completeError(error);
}

/// 記錄請求的 Dio adapter，用來檢查請求標頭、body 與逾時設定。
/// 預設回 200 `{}`；可以指定狀態碼與 body，或用 [errorType] 模擬逾時、斷線。
class RecordingAdapter implements HttpClientAdapter {
  RecordingAdapter({this.statusCode = 200, this.body = '{}', this.errorType});

  final int statusCode;
  final String body;

  /// 有值時不回應，直接拋出這種 [DioException]（例如逾時、斷線）。
  final DioExceptionType? errorType;

  final requests = <RequestOptions>[];

  /// 每個請求實際送出的 body（UTF-8 文字）；沒有 body 時是 null。
  final bodies = <String?>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    bodies.add(
      requestStream == null
          ? null
          : utf8.decode(await requestStream.expand((chunk) => chunk).toList()),
    );
    if (errorType != null) {
      throw DioException(requestOptions: options, type: errorType!);
    }
    return ResponseBody.fromString(
      body,
      statusCode,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

// --- booking ---

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

// --- groups ---

/// 固定時區（預設 UTC+8）的時鐘，測試結果才不受執行電腦的時區影響。
class FixedOffsetClock implements GroupClock {
  FixedOffsetClock(this.nowUtc, {this.offset = const Duration(hours: 8)});

  DateTime nowUtc;
  final Duration offset;

  @override
  DateTime now() => nowUtc;

  @override
  DateTime toLocal(DateTime instant) {
    final wall = instant.toUtc().add(offset);
    return DateTime(
      wall.year,
      wall.month,
      wall.day,
      wall.hour,
      wall.minute,
      wall.second,
    );
  }

  @override
  DateTime fromLocal(DateTime wall) => DateTime.utc(
    wall.year,
    wall.month,
    wall.day,
    wall.hour,
    wall.minute,
    wall.second,
  ).subtract(offset);
}

/// 測試用的揪團資料。時間用 UTC。
Group fakeGroup({
  String id = 'g-1',
  String title = '週末輕策略',
  required DateTime startAt,
  DateTime? endAt,
  int capacity = 4,
  int memberCount = 1,
  int waitlistCount = 0,
  int? fee,
  String status = 'open',
  String organizerId = 'u-org',
  String organizerName = '開團主',
  String shopId = 's-shop',
  String shopName = '測試桌遊店',
  String? myStatus,
}) {
  return Group(
    id: id,
    title: title,
    startAt: startAt,
    endAt: endAt ?? startAt.add(const Duration(hours: 2)),
    capacity: capacity,
    fee: fee,
    status: status,
    shop: ShopRef(id: shopId, name: shopName),
    organizer: UserRef(id: organizerId, displayName: organizerName),
    memberCount: memberCount,
    waitlistCount: waitlistCount,
    remainingSlots: capacity - memberCount < 0 ? 0 : capacity - memberCount,
    myStatus: myStatus,
    createdAt: DateTime.utc(2026, 11, 1),
  );
}

typedef ListCall = ({
  DateTime? startFrom,
  DateTime? startBefore,
  int page,
  int pageSize,
});

/// 在記憶體中運作的 GroupsRepository，記錄每次呼叫。
class FakeGroupsRepository implements GroupsRepository {
  FakeGroupsRepository({List<Group>? groups}) : groups = groups ?? [];

  List<Group> groups;
  final members = <String, List<GroupMember>>{};

  /// list／get 丟出的錯誤。
  Object? error;

  /// 新增、修改、報名、退出丟出的錯誤。
  Object? actionError;

  /// 設定後，報名會等到它完成才回應（用來測試「操作進行中」）。
  Completer<void>? actionGate;
  JoinResult? joinResult;

  final listCalls = <ListCall>[];
  final createCalls = <GroupInput>[];
  final updateCalls = <(String, Map<String, dynamic>)>[];
  final joinCalls = <String>[];
  final removeCalls = <(String, String)>[];

  @override
  Future<GroupPage> list({
    DateTime? startFrom,
    DateTime? startBefore,
    int page = 1,
    int pageSize = 20,
  }) async {
    listCalls.add((
      startFrom: startFrom,
      startBefore: startBefore,
      page: page,
      pageSize: pageSize,
    ));
    if (error != null) throw error!;
    final matched =
        groups
            .where((g) => g.status != 'cancelled')
            .where((g) => startFrom == null || !g.startAt.isBefore(startFrom))
            .where(
              (g) => startBefore == null || g.startAt.isBefore(startBefore),
            )
            .toList()
          ..sort((a, b) => a.startAt.compareTo(b.startAt));
    final start = (page - 1) * pageSize;
    final items = matched.skip(start).take(pageSize).toList();
    return GroupPage(items: items, total: matched.length);
  }

  @override
  Future<Group> get(String id) async {
    if (error != null) throw error!;
    return groups.firstWhere(
      (g) => g.id == id,
      orElse: () => throw const ApiException(
        code: 'GROUP_NOT_FOUND',
        message: '找不到這個揪團',
        statusCode: 404,
      ),
    );
  }

  @override
  Future<List<GroupMember>> listMembers(String id) async => members[id] ?? [];

  @override
  Future<Group> create(GroupInput input) async {
    createCalls.add(input);
    if (actionError != null) throw actionError!;
    final group = fakeGroup(
      id: 'g-new-${createCalls.length}',
      title: input.title,
      startAt: input.startAt,
      endAt: input.endAt,
      capacity: input.capacity,
      fee: input.fee,
      shopId: input.shopId,
      myStatus: 'member',
    );
    groups.add(group);
    return group;
  }

  @override
  Future<Group> update(String id, Map<String, dynamic> changes) async {
    updateCalls.add((id, changes));
    if (actionError != null) throw actionError!;
    final index = groups.indexWhere((g) => g.id == id);
    var group = groups[index];
    if (changes['status'] == 'cancelled') {
      group = group.copyWith(status: 'cancelled');
    }
    if (changes['title'] is String) {
      group = group.copyWith(title: changes['title'] as String);
    }
    groups[index] = group;
    return group;
  }

  @override
  Future<JoinResult> join(String id) async {
    joinCalls.add(id);
    if (actionGate != null) await actionGate!.future;
    if (actionError != null) throw actionError!;
    final result =
        joinResult ?? const JoinResult(userId: 'u-player', status: 'member');
    final index = groups.indexWhere((g) => g.id == id);
    final group = groups[index];
    groups[index] = result.status == 'member'
        ? group.copyWith(
            myStatus: 'member',
            memberCount: group.memberCount + 1,
            remainingSlots: group.remainingSlots - 1,
          )
        : group.copyWith(
            myStatus: 'waitlisted',
            waitlistCount: group.waitlistCount + 1,
          );
    return result;
  }

  @override
  Future<void> removeMember(String groupId, String userId) async {
    removeCalls.add((groupId, userId));
    if (actionError != null) throw actionError!;
    final index = groups.indexWhere((g) => g.id == groupId);
    groups[index] = groups[index].copyWith(myStatus: null);
  }
}
=======
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
