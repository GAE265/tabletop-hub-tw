import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'browser_media_stub.dart'
    if (dart.library.js_interop) 'browser_media_web.dart'
    as impl;

/// 收音（AGENTS.md 5.3：只能在網頁上用的程式包在 core/platform/ 後面）。
///
/// 送出的每一小段都是 16 kHz、單聲道、16 位元 little-endian PCM，
/// 約 32 毫秒一段（host spec §12.2）。
abstract interface class AudioCapture {
  /// 請求麥克風權限。要在玩家點擊之後呼叫。
  /// 允許回 true；拒絕、沒有麥克風或不是 HTTPS 時回 false。
  Future<bool> requestPermission();

  /// 開始收音，每收到一小段就呼叫 [onChunk]。已經在收音時不做事。
  Future<void> start(void Function(Uint8List chunk) onChunk);

  /// 停止收音並放開麥克風。之後可以再 [start]。
  Future<void> stop();
}

final audioCaptureProvider = Provider<AudioCapture>(
  (ref) => impl.createAudioCapture(),
);
