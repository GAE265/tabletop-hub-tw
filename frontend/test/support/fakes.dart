import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:tabletop_hub/core/platform/audio_capture.dart';
import 'package:tabletop_hub/core/platform/audio_playback.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/core/platform/page_visibility.dart';
import 'package:tabletop_hub/core/platform/screen_wake_lock.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_page.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_option.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_search_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
import 'package:tabletop_hub/app/theme/app_fonts.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';

import 'package:tabletop_hub/core/platform/lesson_video_player.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_notification.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/data/shop.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/data/group_input.dart';
import 'package:tabletop_hub/domains/groups/data/group_notification.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import 'package:tabletop_hub/domains/health/data/health_repository.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';
import 'package:tabletop_hub/domains/host/data/hosting_sessions_repository.dart';
import 'package:tabletop_hub/domains/health/data/health_status.dart';
import 'package:tabletop_hub/domains/matches/data/game_match.dart';
import 'package:tabletop_hub/domains/matches/data/match_input.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';

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
    this.seatingPlans = const [],
    this.seatingError,
  });

  List<Shop> shops;
  Object? shopError;
  List<Booking> mine;
  List<Booking> board;
  List<SeatingPlan> seatingPlans;
  Object? seatingError;
  int shopCallCount = 0;
  int seatingCallCount = 0;

  /// 座位圖正式頁面測試用：送出的查詢條件。
  final seatingCalls =
      <({String shopId, String? from, String? to, int? floor})>[];

  /// 首頁測試用：我的訂位丟出的錯誤、等待完成才回應的開關、送出的查詢條件。
  Object? mineError;
  Completer<void>? mineGate;
  final mineCalls = <({String? status, String? fromDate, String? toDate})>[];

  /// 正式頁面測試用：有值時對應的 API 拋出這個錯誤。
  Object? quoteError;
  Object? createError;
  Object? patchError;
  Object? changeTablesError;

  /// 正式頁面測試用：送出的請求。
  final createCalls =
      <
        ({
          String shopId,
          int partySize,
          String startAt,
          String endAt,
          String? specialRequests,
        })
      >[];
  final patchCalls = <({int id, Map<String, dynamic> patch})>[];
  final changeTablesCalls = <({int id, List<int> tableIds})>[];
  final boardQueries = <({String shopId, String from, String to})>[];

  /// 目前使用者的訂位通知，新的在前（add-booking-notifications）。
  List<BookingNotification> notifications = [];

  /// 查詢通知、標成已讀丟出的錯誤。
  Object? notificationsError;
  Object? markReadError;

  /// 標成已讀時寫入的時間。
  DateTime readAt = DateTime.utc(2026, 11, 14, 4, 30);
  final notificationCalls = <({int page, int pageSize})>[];
  final markReadCalls = <String>[];

  @override
  Future<BookingNotificationPage> listNotifications({
    int page = 1,
    int pageSize = 20,
  }) async {
    notificationCalls.add((page: page, pageSize: pageSize));
    if (notificationsError != null) throw notificationsError!;
    return BookingNotificationPage(
      items: notifications.skip((page - 1) * pageSize).take(pageSize).toList(),
      total: notifications.length,
      unreadCount: notifications.where((n) => n.readAt == null).length,
    );
  }

  @override
  Future<BookingNotification> markNotificationRead(String id) async {
    markReadCalls.add(id);
    if (markReadError != null) throw markReadError!;
    final index = notifications.indexWhere((n) => n.id == id);
    final read = notifications[index].readAt == null
        ? notifications[index].copyWith(readAt: readAt)
        : notifications[index];
    notifications[index] = read;
    return read;
  }

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
  }) async {
    if (quoteError != null) throw quoteError!;
    return QuoteResult(
      startAt: startAt,
      endAt: endAt,
      fee: const Fee(billableHours: '2.00', venueFee: '480.00'),
      tableCodes: ['T1'],
    );
  }

  @override
  Future<Booking> create({
    required String shopId,
    required int partySize,
    required String startAt,
    required String endAt,
    String? specialRequests,
    bool confirmOverlap = false,
  }) async {
    if (createError != null) throw createError!;
    createCalls.add((
      shopId: shopId,
      partySize: partySize,
      startAt: startAt,
      endAt: endAt,
      specialRequests: specialRequests,
    ));
    return Booking(
      shopName: '測試店',
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
  }

  @override
  Future<Booking> get(int id) => throw UnimplementedError();

  /// 只支援改狀態：從 [mine] 或 [board] 找到訂位，回傳改好狀態的新訂位。
  @override
  Future<Booking> patch(int id, Map<String, dynamic> patch) async {
    patchCalls.add((id: id, patch: patch));
    if (patchError != null) throw patchError!;
    final b = [...mine, ...board].firstWhere((x) => x.id == id);
    return Booking(
      shopName: '測試店',
      id: b.id,
      reservationCode: b.reservationCode,
      shopId: b.shopId,
      startAt: b.startAt,
      endAt: b.endAt,
      partySize: b.partySize,
      status: patch['status'] as String? ?? b.status,
      tableCodes: b.tableCodes,
      estimatedFee: b.estimatedFee,
      finalFee: patch['status'] == 'completed' ? '480.00' : b.finalFee,
      notice: b.notice,
    );
  }

  /// 換桌：記下請求，回傳把桌位換成 `T<id>` 的新訂位。
  @override
  Future<Booking> changeTables(int id, List<int> tableIds) async {
    changeTablesCalls.add((id: id, tableIds: tableIds));
    if (changeTablesError != null) throw changeTablesError!;
    final b = [...mine, ...board].firstWhere((x) => x.id == id);
    return Booking(
      shopName: '測試店',
      id: b.id,
      reservationCode: b.reservationCode,
      shopId: b.shopId,
      startAt: b.startAt,
      endAt: b.endAt,
      partySize: b.partySize,
      status: b.status,
      tableCodes: [for (final t in tableIds) 'T$t'],
      estimatedFee: b.estimatedFee,
      finalFee: b.finalFee,
      notice: b.notice,
    );
  }

  @override
  Future<BookingPage> listMine({
    String? status,
    String? fromDate,
    String? toDate,
  }) async {
    mineCalls.add((status: status, fromDate: fromDate, toDate: toDate));
    if (mineGate case final gate?) await gate.future;
    if (mineError != null) throw mineError!;
    return BookingPage(items: mine, total: mine.length);
  }

  @override
  Future<BookingPage> listForShop({
    required String shopId,
    required String from,
    required String to,
  }) async {
    boardQueries.add((shopId: shopId, from: from, to: to));
    return BookingPage(items: board, total: board.length);
  }

  @override
  Future<List<SeatingPlan>> getTablesStatus({
    required String shopId,
    String? from,
    String? to,
    int? floor,
  }) async {
    seatingCallCount++;
    seatingCalls.add((shopId: shopId, from: from, to: to, floor: floor));
    if (seatingError != null) throw seatingError!;
    return seatingPlans;
  }
}

const fakeShopA = Shop(id: 's-a', name: '甲店');
const fakeShopB = Shop(id: 's-b', name: '乙店');

/// 一則訂位通知；預設是台灣時間 11/22（日）19:00–21:00、4 人、在甲店。
/// [readAt] 為 null 代表未讀。
BookingNotification fakeBookingNotification({
  String id = 'bn-1',
  String type = 'booking_confirmed',
  int bookingId = 7,
  String shopName = '甲店',
  DateTime? startAt,
  DateTime? endAt,
  int partySize = 4,
  DateTime? readAt,
  DateTime? createdAt,
}) => BookingNotification(
  id: id,
  type: type,
  booking: BookingNotificationRef(
    id: bookingId,
    reservationCode: 'BK$bookingId',
    shopName: shopName,
    startAt: startAt ?? DateTime.utc(2026, 11, 22, 11),
    endAt: endAt ?? DateTime.utc(2026, 11, 22, 13),
    partySize: partySize,
  ),
  readAt: readAt,
  createdAt: createdAt ?? DateTime.utc(2026, 11, 14, 3),
);

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
  List<GameRef> games = const [],
  DateTime? confirmedAt,
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
    games: games,
    confirmedAt: confirmedAt,
    createdAt: DateTime.utc(2026, 11, 1),
  );
}

/// 一則揪團通知；[readAt] 為 null 代表未讀。
GroupNotification fakeNotification({
  String id = 'n-1',
  String type = 'group_confirmed',
  String groupId = 'g-1',
  String groupTitle = '週末輕策略',
  DateTime? groupStartAt,
  DateTime? readAt,
  DateTime? createdAt,
}) => GroupNotification(
  id: id,
  type: type,
  group: NotificationGroupRef(
    id: groupId,
    title: groupTitle,
    startAt: groupStartAt ?? DateTime.utc(2026, 11, 21, 11),
  ),
  readAt: readAt,
  createdAt: createdAt ?? DateTime.utc(2026, 11, 14, 3),
);

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

  /// `GET /api/v1/shops` 的店家。
  List<ShopRef> shops = const [
    ShopRef(id: 's-shop', name: '測試桌遊店'),
    ShopRef(id: 's-other', name: '另一間店'),
  ];

  /// `GET /api/v1/games` 的遊戲（全部）。
  List<GameRef> games = const [
    GameRef(id: 1, name: '阿瓦隆'),
    GameRef(id: 2, name: '阿不思學院'),
    GameRef(id: 3, name: '馬可波羅'),
  ];

  /// 店家清單、遊戲清單丟出的錯誤。
  Object? shopsError;
  Object? gamesError;
  int shopsCalls = 0;
  int gamesCalls = 0;
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

  /// 目前使用者的通知，新的在前。
  List<GroupNotification> notifications = [];

  /// 查詢通知、標成已讀丟出的錯誤。
  Object? notificationsError;
  Object? markReadError;

  /// 標成已讀時寫入的時間。
  DateTime readAt = DateTime.utc(2026, 11, 14, 4, 30);
  final notificationCalls = <({int page, int pageSize})>[];
  final markReadCalls = <String>[];

  @override
  Future<GroupNotificationPage> listNotifications({
    int page = 1,
    int pageSize = 20,
  }) async {
    notificationCalls.add((page: page, pageSize: pageSize));
    if (notificationsError != null) throw notificationsError!;
    return GroupNotificationPage(
      items: notifications.skip((page - 1) * pageSize).take(pageSize).toList(),
      total: notifications.length,
      unreadCount: notifications.where((n) => n.readAt == null).length,
    );
  }

  @override
  Future<GroupNotification> markNotificationRead(String id) async {
    markReadCalls.add(id);
    if (markReadError != null) throw markReadError!;
    final index = notifications.indexWhere((n) => n.id == id);
    final read = notifications[index].readAt == null
        ? notifications[index].copyWith(readAt: readAt)
        : notifications[index];
    notifications[index] = read;
    return read;
  }

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
  Future<List<ShopRef>> listShops() async {
    shopsCalls++;
    if (shopsError != null) throw shopsError!;
    return shops;
  }

  @override
  Future<List<GameRef>> listGames() async {
    gamesCalls++;
    if (gamesError != null) throw gamesError!;
    return games;
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
      games: [
        for (final id in input.gameIds) games.firstWhere((g) => g.id == id),
      ],
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
    if (changes['confirmed'] == true) {
      group = group.copyWith(confirmedAt: DateTime.utc(2026, 11, 14, 4));
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

/// 在記憶體中運作的 RulesQaRepository。發問會等到 [respond] 或 [fail] 才回應。
class FakeRulesQaRepository implements RulesQaRepository {
  FakeRulesQaRepository({
    List<RulesLessonSummary>? lessons,
    Map<int, RulesLesson>? details,
  }) : lessons = lessons ?? [],
       details = details ?? {};

  List<RulesLessonSummary> lessons;
  Map<int, RulesLesson> details;

  /// 清單、教學內容丟出的錯誤。
  Object? listError;
  Object? lessonError;

  final requests = <(int, RulesMessageRequest)>[];
  final _pending = <Completer<RulesAnswer>>[];

  @override
  Future<List<RulesLessonSummary>> listLessons() async {
    if (listError != null) throw listError!;
    return lessons;
  }

  @override
  Future<RulesLesson> getLesson(int gameId) async {
    if (lessonError != null) throw lessonError!;
    final lesson = details[gameId];
    if (lesson == null) {
      throw const ApiException(
        code: 'RULES_LESSON_NOT_FOUND',
        message: '這款遊戲還沒有教材',
        statusCode: 404,
      );
    }
    return lesson;
  }

  @override
  Future<RulesAnswer> sendMessage(int gameId, RulesMessageRequest request) {
    requests.add((gameId, request));
    final completer = Completer<RulesAnswer>();
    _pending.add(completer);
    return completer.future;
  }

  /// 最早那個還在等的發問收到回答。
  void respond(RulesAnswer answer) => _pending.removeAt(0).complete(answer);

  /// 最早那個還在等的發問失敗。
  void fail(Object error) => _pending.removeAt(0).completeError(error);
}

/// 不載入 YouTube 的影片播放器：只顯示影片 ID，讓 widget 測試能檢查有沒有放播放器。
class FakeLessonVideoPlayer implements LessonVideoPlayer {
  const FakeLessonVideoPlayer();

  @override
  Widget build(BuildContext context, LessonVideo video) => SizedBox(
    key: const Key('fake-video-player'),
    height: 180,
    child: Text('影片：${video.youtubeId ?? video.videoUrl}'),
  );
}

class FakeImagePicker implements ImagePicker {
  List<PickedImage>? images;
  Object? error;
  int calls = 0;

  @override
  Future<List<PickedImage>?> pickImages() async {
    calls++;
    if (error != null) throw error!;
    return images;
  }
}

class FakeGameSearchRepository implements GameSearchRepository {
  List<GameOption> allGames;
  Object? error;

  FakeGameSearchRepository({this.allGames = const [], this.error});

  int searchCalls = 0;
  int listAllCalls = 0;

  @override
  Future<List<GameOption>> search(String name) async {
    searchCalls++;
    if (error != null) throw error!;
    return allGames;
  }

  @override
  Future<List<GameOption>> listAll() async {
    listAllCalls++;
    if (error != null) throw error!;
    return allGames;
  }
}

class FakeManualPagesRepository implements ManualPagesRepository {
  final imports = <({int gamesId, int page, PickedImage image})>[];
  final rows = <int, String>{};
  final failures = <int, Object>{};
  final lists = <int>[];
  String ocrProvider = 'fake';
  Object? listError;
  Completer<void>? importGate;
  Completer<void>? listGate;
  int active = 0;
  int maxActive = 0;

  @override
  Future<ManualPage> importPage(
    int gamesId,
    int page,
    PickedImage image,
  ) async {
    imports.add((gamesId: gamesId, page: page, image: image));
    active++;
    if (active > maxActive) maxActive = active;
    try {
      if (importGate != null) await importGate!.future;
      if (failures[page] != null) throw failures[page]!;
      final content = '# ${image.name}';
      rows[page] = content;
      return ManualPage(page: page, content: content);
    } finally {
      active--;
    }
  }

  @override
  Future<ManualPageList> list(int gamesId) async {
    lists.add(gamesId);
    if (listGate != null) await listGate!.future;
    if (listError != null) throw listError!;
    final pages = rows.keys.toList()..sort();
    return ManualPageList(
      items: [
        for (final page in pages) ManualPage(page: page, content: rows[page]!),
      ],
      total: rows.length,
      ocrProvider: ocrProvider,
    );
  }
}

class FakeManualPagesAdapter implements HttpClientAdapter {
  final requests = <RequestOptions>[];
  final bodies = <String>[];
  int status = 200;
  Map<String, dynamic> response = {
    'games_id': 1,
    'page': 1,
    'content': '# title',
  };

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    if (requestStream != null) {
      final bytes = <int>[];
      await for (final chunk in requestStream) {
        bytes.addAll(chunk);
      }
      bodies.add(latin1.decode(bytes));
    }
    return ResponseBody.fromString(
      jsonEncode(response),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

// --- matches ---

const fakeMatchId = 'm-1';

MatchParticipant fakeMatchParticipant({
  String id = 'p-1',
  int seatNumber = 1,
  String? userId = 'u-player',
  String displayName = '測試玩家',
  String? faction,
  bool? isWinner,
  bool isConfirmed = false,
}) => MatchParticipant(
  id: id,
  seatNumber: seatNumber,
  userId: userId,
  displayName: displayName,
  faction: faction,
  isWinner: isWinner,
  isConfirmed: isConfirmed,
);

MatchTurn fakeMatchTurn({
  int turnNumber = 1,
  int? seatNumber = 1,
  Map<String, dynamic>? gameData,
  String recordedBy = 'u-player',
}) => MatchTurn(
  id: 't-$turnNumber',
  turnNumber: turnNumber,
  seatNumber: seatNumber,
  gameData:
      gameData ?? const WhiteRoseTurnData(playedSeatNumbers: [1, 2]).toJson(),
  recordedBy: recordedBy,
  updatedAt: DateTime.utc(2026, 11, 20, 12),
);

/// 預設是《血與刃的白薔薇》進行中的一局：座位 1 測試玩家（開局者）、
/// 2 玩家乙（有帳號）、3 Amy（沒有帳號）。
GameMatch fakeMatch({
  String id = fakeMatchId,
  String status = 'in_progress',
  List<MatchParticipant>? participants,
  List<MatchTurn> turns = const [],
  Map<String, dynamic>? result,
}) {
  final people =
      participants ??
      [
        fakeMatchParticipant(),
        fakeMatchParticipant(
          id: 'p-2',
          seatNumber: 2,
          userId: 'u-b',
          displayName: '玩家乙',
        ),
        fakeMatchParticipant(
          id: 'p-3',
          seatNumber: 3,
          userId: null,
          displayName: 'Amy',
        ),
      ];
  return _recount(
    GameMatch(
      id: id,
      game: const MatchGameRef(id: 1, name: '血與刃的白薔薇'),
      playedOn: DateTime.utc(2026, 11, 20),
      locationType: 'home',
      createdBy: const MatchUserRef(id: 'u-player', displayName: '測試玩家'),
      status: status,
      result: result,
      participants: people,
      turns: turns,
      participantCount: 0,
      accountCount: 0,
      confirmedCount: 0,
      isValid: false,
      createdAt: DateTime.utc(2026, 11, 20, 12),
      updatedAt: DateTime.utc(2026, 11, 20, 12),
    ),
  );
}

/// 重新計算「幾人參加、幾人有帳號、幾人已確認」與是否有效（後端也是這樣算）。
GameMatch _recount(GameMatch match) {
  final accounts = match.participants.where((p) => p.userId != null).toList();
  final confirmed = accounts.where((p) => p.isConfirmed).length;
  return match.copyWith(
    participantCount: match.participants.length,
    accountCount: accounts.length,
    confirmedCount: confirmed,
    isValid: match.status == 'finished' && confirmed == accounts.length,
  );
}

/// 在記憶體中模擬後端的規則：同一回合／同一結果已有紀錄時回 409，帶 overwrite 才覆蓋；
/// 記錄結果的人自動確認；覆蓋結果清除其他人的確認。
class FakeMatchesRepository implements MatchesRepository {
  FakeMatchesRepository({GameMatch? match, this.currentUserId = 'u-player'})
    : match = match ?? fakeMatch();

  GameMatch match;

  /// 模擬後端認得的「目前使用者」（自己加入、記錄結果的人自動確認用）。
  String currentUserId;

  /// get／list 丟出的錯誤。
  Object? error;

  /// 正式頁面測試用：「最近的局」回傳的清單；null 時回傳 [match] 一筆。
  List<GameMatch>? listItems;

  /// 所有寫入操作丟出的錯誤。
  Object? actionError;

  /// 設定後，寫入操作會等到它完成才回應（用來測試「操作進行中」）。
  Completer<void>? actionGate;

  final getCalls = <String>[];
  final createCalls = <MatchInput>[];

  /// 每次 `list` 帶的 `group_id`（沒帶是 null）。
  final listGroupIds = <String?>[];
  final addCalls = <ParticipantInput>[];
  final confirmCalls = <String>[];
  final removeCalls = <String>[];
  final turnCalls = <({TurnInput input, bool overwrite})>[];
  final resultCalls = <({ResultInput input, bool overwrite})>[];

  Future<void> _write() async {
    if (actionGate != null) await actionGate!.future;
    if (actionError != null) throw actionError!;
  }

  @override
  Future<MatchPage> list({
    int? gameId,
    String? groupId,
    String? userId,
    int page = 1,
    int pageSize = 20,
  }) async {
    listGroupIds.add(groupId);
    if (error != null) throw error!;
    final items = listItems ?? [match];
    return MatchPage(items: items, total: items.length);
  }

  @override
  Future<GameMatch> get(String id) async {
    getCalls.add(id);
    if (error != null) throw error!;
    return match;
  }

  @override
  Future<GameMatch> create(MatchInput input) async {
    createCalls.add(input);
    await _write();
    final creator = fakeMatchParticipant(
      seatNumber: input.seatNumber ?? 1,
      userId: currentUserId,
      isConfirmed: false,
    );
    match = fakeMatch(
      participants: [creator],
    ).copyWith(locationType: input.locationType);
    return match;
  }

  @override
  Future<MatchParticipant> addParticipant(
    String matchId,
    ParticipantInput input,
  ) async {
    addCalls.add(input);
    await _write();
    final taken = match.participants.map((p) => p.seatNumber).toSet();
    var seat = input.seatNumber ?? 1;
    if (input.seatNumber == null) {
      while (taken.contains(seat)) {
        seat++;
      }
    }
    final named = input.displayName != null;
    final participant = fakeMatchParticipant(
      id: 'p-new-${match.participants.length + 1}',
      seatNumber: seat,
      userId: named ? null : currentUserId,
      displayName: input.displayName ?? '測試玩家',
    );
    match = _recount(
      match.copyWith(participants: [...match.participants, participant]),
    );
    return participant;
  }

  @override
  Future<MatchParticipant> confirm(String matchId, String participantId) async {
    confirmCalls.add(participantId);
    await _write();
    final updated = [
      for (final p in match.participants)
        p.id == participantId ? p.copyWith(isConfirmed: true) : p,
    ];
    match = _recount(match.copyWith(participants: updated));
    return match.participants.firstWhere((p) => p.id == participantId);
  }

  @override
  Future<void> removeParticipant(String matchId, String participantId) async {
    removeCalls.add(participantId);
    await _write();
    final target = match.participants.firstWhere((p) => p.id == participantId);
    final used = match.turns.where(
      (t) =>
          t.seatNumber == target.seatNumber ||
          (t.gameData['played_seat_numbers'] as List).contains(
            target.seatNumber,
          ),
    );
    if (used.isNotEmpty) {
      throw ApiException(
        code: 'MATCH_PARTICIPANT_HAS_TURNS',
        message: '座位 ${target.seatNumber} 已出現在回合，不能移除',
        statusCode: 409,
        details: {
          'seat_number': target.seatNumber,
          'turn_numbers': [for (final t in used) t.turnNumber],
        },
      );
    }
    match = _recount(
      match.copyWith(
        participants: [
          for (final p in match.participants)
            if (p.id != participantId) p,
        ],
      ),
    );
  }

  @override
  Future<({MatchTurn turn, bool created})> recordTurn(
    String matchId,
    TurnInput input, {
    bool overwrite = false,
  }) async {
    turnCalls.add((input: input, overwrite: overwrite));
    await _write();
    final index = match.turns.indexWhere(
      (t) => t.turnNumber == input.turnNumber,
    );
    if (index >= 0 && !overwrite) {
      final existing = match.turns[index];
      throw ApiException(
        code: 'MATCH_TURN_ALREADY_RECORDED',
        message: '第 ${input.turnNumber} 回合已經有紀錄',
        statusCode: 409,
        details: {
          'existing': {
            'turn_number': existing.turnNumber,
            'seat_number': existing.seatNumber,
            'game_data': existing.gameData,
            'recorded_by': existing.recordedBy,
          },
        },
      );
    }
    final turn = fakeMatchTurn(
      turnNumber: input.turnNumber,
      seatNumber: input.seatNumber,
      gameData: input.gameData,
      recordedBy: currentUserId,
    );
    final turns = [...match.turns];
    if (index >= 0) {
      turns[index] = turn;
    } else {
      turns.add(turn);
      turns.sort((a, b) => a.turnNumber.compareTo(b.turnNumber));
    }
    match = match.copyWith(turns: turns);
    return (turn: turn, created: index < 0);
  }

  @override
  Future<GameMatch> recordResult(
    String matchId,
    ResultInput input, {
    bool overwrite = false,
  }) async {
    resultCalls.add((input: input, overwrite: overwrite));
    await _write();
    if (match.result != null && !overwrite) {
      throw ApiException(
        code: 'MATCH_RESULT_ALREADY_RECORDED',
        message: '這一局已經有結果',
        statusCode: 409,
        details: {'result': match.result},
      );
    }
    final people = [
      for (final p in match.participants)
        p.copyWith(
          faction: input.factions[p.seatNumber],
          isWinner: input.factions[p.seatNumber] == input.winningFaction,
          // 記錄結果的人自動確認，其他人的確認清除
          isConfirmed: p.userId == currentUserId,
        ),
    ];
    match = _recount(
      match.copyWith(
        status: 'finished',
        result: {'type': 'faction', 'winning_faction': input.winningFaction},
        participants: people,
      ),
    );
    return match;
  }
}

// --- host（AI 語音主持）---

/// 收音、播音、常亮、連線各個 fake 共用的呼叫紀錄，用來確認先後順序。
typedef HostCallLog = List<String>;

class FakeAudioCapture implements AudioCapture {
  FakeAudioCapture({HostCallLog? log}) : log = log ?? [];

  final HostCallLog log;

  /// 設成 false 模擬玩家拒絕麥克風。
  bool permissionGranted = true;
  bool capturing = false;
  int startCount = 0;
  int stopCount = 0;
  void Function(Uint8List chunk)? _onChunk;

  /// 模擬麥克風送出一小段 PCM。
  void emit(Uint8List chunk) {
    if (capturing) _onChunk?.call(chunk);
  }

  @override
  Future<bool> requestPermission() async {
    log.add('mic.request');
    return permissionGranted;
  }

  @override
  Future<void> start(void Function(Uint8List chunk) onChunk) async {
    log.add('mic.start');
    startCount++;
    capturing = true;
    _onChunk = onChunk;
  }

  @override
  Future<void> stop() async {
    stopCount++;
    capturing = false;
    _onChunk = null;
  }
}

class FakeAudioPlayback implements AudioPlayback {
  /// 設成 false 模擬瀏覽器不讓出聲。
  bool unlockResult = true;
  bool _unlocked = false;
  int unlockCount = 0;
  int clearCount = 0;

  /// 已排進、還沒被清掉的聲音。
  final queued = <Uint8List>[];
  final _segmentEnds = <void Function()>[];

  /// 模擬排進去的聲音都播完了：通知每一段的播完。
  void finishSegments() {
    final callbacks = List.of(_segmentEnds);
    _segmentEnds.clear();
    queued.clear();
    for (final callback in callbacks) {
      callback();
    }
  }

  @override
  bool get isUnlocked => _unlocked;

  @override
  Future<bool> unlock() async {
    unlockCount++;
    _unlocked = unlockResult;
    return unlockResult;
  }

  @override
  void enqueue(Uint8List pcm) => queued.add(pcm);

  @override
  void markSegmentEnd(void Function() onPlayed) => _segmentEnds.add(onPlayed);

  @override
  void clear() {
    clearCount++;
    queued.clear();
    _segmentEnds.clear();
  }
}

class FakeScreenWakeLock implements ScreenWakeLock {
  FakeScreenWakeLock({HostCallLog? log}) : log = log ?? [];

  final HostCallLog log;

  /// 設成 false 模擬系統拒絕常亮。
  bool granted = true;
  bool held = false;
  int releaseCount = 0;

  @override
  Future<bool> request() async {
    log.add('wakeLock.request');
    held = granted;
    return granted;
  }

  @override
  Future<void> release() async {
    releaseCount++;
    held = false;
  }
}

class FakePageVisibility implements PageVisibility {
  final _changes = StreamController<bool>.broadcast(sync: true);
  bool _visible = true;

  void hide() {
    _visible = false;
    _changes.add(false);
  }

  void show() {
    _visible = true;
    _changes.add(true);
  }

  @override
  bool get isVisible => _visible;

  @override
  Stream<bool> get changes => _changes.stream;
}

/// 測試用的一場主持：預設剛開、在開場。
HostingSession fakeHostingSession({
  String id = 'h-1',
  HostStatus status = HostStatus.active,
  int playerCount = 7,
  TurnTakingMode turnTakingMode = TurnTakingMode.auto,
  HostVoice voice = HostVoice.male,
  HostStep step = HostStep.opening,
  int? turnNumber,
  int? phaseNumber,
  bool paused = false,
  HostWinner? winner,
}) => HostingSession(
  id: id,
  status: status,
  playerCount: playerCount,
  turnTakingMode: turnTakingMode,
  voice: voice,
  step: step,
  turnNumber: turnNumber,
  phaseNumber: phaseNumber,
  paused: paused,
  winner: winner,
  createdAt: DateTime.utc(2026, 11, 22, 12),
);

class FakeHostingSessionsRepository implements HostingSessionsRepository {
  FakeHostingSessionsRepository({
    List<HostingSession>? sessions,
    HostCallLog? log,
  }) : sessions = sessions ?? [],
       log = log ?? [];

  List<HostingSession> sessions;
  final HostCallLog log;
  Object? listError;
  Object? createError;
  Object? connectError;
  final createRequests = <CreateHostingSessionRequest>[];
  final connectCalls = <({String id, TurnTakingMode? turnTakingMode})>[];
  int _ticketCount = 0;

  HostConnectionTicket _ticket() => HostConnectionTicket(
    ticket: 't-${++_ticketCount}',
    expiresAt: DateTime.utc(2026, 11, 22, 12, 1),
  );

  @override
  Future<List<HostingSession>> list() async {
    if (listError != null) throw listError!;
    return sessions;
  }

  @override
  Future<HostingSessionAccess> create(
    CreateHostingSessionRequest request,
  ) async {
    log.add('POST');
    createRequests.add(request);
    if (createError != null) throw createError!;
    final session = fakeHostingSession(
      playerCount: request.playerCount,
      turnTakingMode: request.turnTakingMode,
      voice: request.voice,
    );
    sessions = [session];
    return HostingSessionAccess(session: session, connection: _ticket());
  }

  @override
  Future<HostingSessionAccess> connect(
    String id, {
    TurnTakingMode? turnTakingMode,
  }) async {
    log.add('connections');
    connectCalls.add((id: id, turnTakingMode: turnTakingMode));
    if (connectError != null) throw connectError!;
    final current = sessions.firstWhere(
      (session) => session.id == id,
      orElse: () => fakeHostingSession(id: id),
    );
    final session = turnTakingMode == null
        ? current
        : current.copyWith(turnTakingMode: turnTakingMode);
    sessions = [session];
    return HostingSessionAccess(session: session, connection: _ticket());
  }
}

/// 手寫的 WebSocket 通道：記下裝置送出的訊息，測試用 [emit] 假裝後端送來訊息。
class FakeHostStream implements HostStream {
  FakeHostStream({required this.sessionId, required this.ticket});

  final String sessionId;
  final String ticket;
  final _messages = StreamController<HostServerMessage>(sync: true);

  /// 裝置送出的 JSON 訊息（照 spec §12.3 的格式）。
  final sentJson = <Map<String, dynamic>>[];

  /// 裝置送出的聲音。
  final sentAudio = <Uint8List>[];
  bool closed = false;

  void emit(HostServerMessage message) => _messages.add(message);

  /// 模擬後端關掉連線。
  void serverClose() => _messages.close();

  @override
  Stream<HostServerMessage> get messages => _messages.stream;

  @override
  void send(HostClientMessage message) {
    if (closed) return;
    sentJson.add(message.toJson());
  }

  @override
  void sendAudio(Uint8List pcm) {
    if (closed) return;
    sentAudio.add(pcm);
  }

  @override
  Future<void> close() async {
    closed = true;
    if (!_messages.isClosed) await _messages.close();
  }
}

class FakeHostStreamConnector implements HostStreamConnector {
  FakeHostStreamConnector({HostCallLog? log}) : log = log ?? [];

  final HostCallLog log;
  Object? error;
  final streams = <FakeHostStream>[];

  FakeHostStream get current => streams.last;

  @override
  Future<HostStream> connect(String sessionId, String ticket) async {
    log.add('ws.connect');
    if (error != null) throw error!;
    final stream = FakeHostStream(sessionId: sessionId, ticket: ticket);
    streams.add(stream);
    return stream;
  }
}
