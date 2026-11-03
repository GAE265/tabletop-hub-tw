import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 只能在網頁或手機上用的功能，一律包在這類介面後面（AGENTS.md 5.3），
/// 之後轉 Android／iOS 時只需新增實作，呼叫端不必改。
abstract interface class PlatformInfo {
  bool get isWeb;
}

class DefaultPlatformInfo implements PlatformInfo {
  const DefaultPlatformInfo();

  @override
  bool get isWeb => kIsWeb;
}

final platformInfoProvider = Provider<PlatformInfo>(
  (ref) => const DefaultPlatformInfo(),
);
