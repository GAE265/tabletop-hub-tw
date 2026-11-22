import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'browser_media_stub.dart'
    if (dart.library.js_interop) 'browser_media_web.dart'
    as impl;

/// 頁面看不看得見：切到別的分頁、別的 App 或鎖屏時看不見。
abstract interface class PageVisibility {
  bool get isVisible;

  /// 看得見與否改變時送出新的值（true 是看得見）。
  Stream<bool> get changes;
}

final pageVisibilityProvider = Provider<PageVisibility>(
  (ref) => impl.createPageVisibility(),
);
