import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'browser_media_stub.dart'
    if (dart.library.js_interop) 'browser_media_web.dart'
    as impl;

/// 播音：邊收到邊播 24 kHz、單聲道、16 位元 little-endian PCM（host spec §12.2）。
abstract interface class AudioPlayback {
  /// 瀏覽器已經允許出聲。
  bool get isUnlocked;

  /// 瀏覽器要玩家先點一下才能出聲：在點擊的處理流程一開始呼叫（不要先 await 別的事）。
  /// 允許出聲回 true。
  Future<bool> unlock();

  /// 把一小段聲音排在目前待播內容的後面。
  void enqueue(Uint8List pcm);

  /// 到目前為止排進去的聲音全部播完時呼叫 [onPlayed]。
  /// 在那之前呼叫了 [clear]，[onPlayed] 就不會被呼叫（被打斷不算播完）。
  void markSegmentEnd(void Function() onPlayed);

  /// 立刻停播並清空待播內容。
  void clear();
}

final audioPlaybackProvider = Provider<AudioPlayback>(
  (ref) => impl.createAudioPlayback(),
);
