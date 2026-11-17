import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 由 `--dart-define` 注入的執行期設定。前端不放任何秘密（AGENTS.md 5.3）。
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.showPrototypes,
    required this.devUserEnabled,
  });

  /// `--dart-define=API_BASE_URL=...`；未指定時打相對路徑（同 host，port 8000 需反向代理）。
  /// 開發時建議用 `--dart-define=API_BASE_URL=http://<host>:8000` 指定後端位址。
  factory AppConfig.fromEnvironment() {
    const apiBaseUrl = String.fromEnvironment('API_BASE_URL');
    const showPrototypes = bool.fromEnvironment('SHOW_PROTOTYPES');
    const devUserFlag = bool.fromEnvironment(
      'DEV_USER_ENABLED',
      defaultValue: true,
    );
    return const AppConfig(
      apiBaseUrl: apiBaseUrl,
      showPrototypes: showPrototypes,
      // release 建置一律關閉，不能靠旗標打開。
      devUserEnabled: devUserFlag && !kReleaseMode,
    );
  }

  final String apiBaseUrl;

  /// `--dart-define=SHOW_PROTOTYPES=true` 才掛上 `/proto/...` 路由。
  final bool showPrototypes;

  /// 開發環境才帶 `X-Dev-User` 並顯示身分切換器。
  final bool devUserEnabled;
}

final appConfigProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);
