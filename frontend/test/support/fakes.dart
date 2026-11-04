import 'package:dio/dio.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
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
