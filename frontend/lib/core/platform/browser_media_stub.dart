import 'dart:typed_data';

import 'audio_capture.dart';
import 'audio_playback.dart';
import 'page_visibility.dart';
import 'screen_wake_lock.dart';

// 🚧 Android／iOS 的收音播音之後再做（host spec §14.1）。目前非網頁平台只放佔位實作，
// 測試一律用 test/support/fakes.dart 的 fake 取代。

AudioCapture createAudioCapture() => const _UnsupportedAudioCapture();
AudioPlayback createAudioPlayback() => const _UnsupportedAudioPlayback();
ScreenWakeLock createScreenWakeLock() => const _NoScreenWakeLock();
PageVisibility createPageVisibility() => const _AlwaysVisible();

class _UnsupportedAudioCapture implements AudioCapture {
  const _UnsupportedAudioCapture();

  @override
  Future<bool> requestPermission() async => false;

  @override
  Future<void> start(void Function(Uint8List chunk) onChunk) =>
      throw UnsupportedError('收音目前只支援網頁');

  @override
  Future<void> stop() async {}
}

class _UnsupportedAudioPlayback implements AudioPlayback {
  const _UnsupportedAudioPlayback();

  @override
  bool get isUnlocked => false;

  @override
  Future<bool> unlock() async => false;

  @override
  void enqueue(Uint8List pcm) {}

  @override
  void markSegmentEnd(void Function() onPlayed) {}

  @override
  void clear() {}
}

class _NoScreenWakeLock implements ScreenWakeLock {
  const _NoScreenWakeLock();

  @override
  Future<bool> request() async => false;

  @override
  Future<void> release() async {}
}

class _AlwaysVisible implements PageVisibility {
  const _AlwaysVisible();

  @override
  bool get isVisible => true;

  @override
  Stream<bool> get changes => const Stream.empty();
}
