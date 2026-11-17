import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_page.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_option.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/game_search_repository.dart';
import 'package:tabletop_hub/domains/rules_ingest/data/manual_pages_repository.dart';
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
