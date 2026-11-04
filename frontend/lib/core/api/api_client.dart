import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../dev/state/dev_user_state.dart';

Dio _newDio(AppConfig config) => Dio(
  BaseOptions(
    baseUrl: config.apiBaseUrl,
    headers: {'Accept': 'application/json'},
  ),
);

/// 不帶身分標頭的 Dio，給「取得測試帳號清單」用。
/// 與 [dioProvider] 分開是為了避免 清單 → 標頭 → 清單 的循環相依。
final rawDioProvider = Provider<Dio>(
  (ref) => _newDio(ref.watch(appConfigProvider)),
);

/// 所有 domain 的 repository 共用的 API client。
/// 開發環境下自動帶 `X-Dev-User`；正式環境完全不帶（AGENTS.md 4.5）。
final dioProvider = Provider<Dio>((ref) {
  final config = ref.watch(appConfigProvider);
  final dio = _newDio(config);
  if (config.devUserEnabled) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final header = ref.read(devUserHeaderProvider);
          if (header != null) options.headers['X-Dev-User'] = header;
          handler.next(options);
        },
      ),
    );
  }
  return dio;
});
