import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
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
