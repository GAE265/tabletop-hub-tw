import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'browser_media_stub.dart'
    if (dart.library.js_interop) 'browser_media_web.dart'
    as impl;

/// 螢幕常亮。頁面被切走時系統會自動放開，回來後要再要求一次。
abstract interface class ScreenWakeLock {
  /// 要求螢幕常亮。系統拒絕或瀏覽器不支援時回 false。
  Future<bool> request();

  /// 不再需要常亮。
  Future<void> release();
}

final screenWakeLockProvider = Provider<ScreenWakeLock>(
  (ref) => impl.createScreenWakeLock(),
);
