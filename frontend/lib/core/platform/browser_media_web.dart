import 'dart:async';
import 'dart:js_interop';
import 'dart:math' as math;
import 'dart:typed_data';

import 'audio_capture.dart';
import 'audio_playback.dart';
import 'page_visibility.dart';
import 'screen_wake_lock.dart';
import 'pcm16.dart';

// 網頁版的收音、播音、螢幕常亮、頁面看不看得見（host spec §14.1）。
// 直接用瀏覽器的 API，不加音訊套件（spec 預設 7）；只用 SDK 內建的 dart:js_interop，
// 不另外宣告 package:web。做法照原型 .scratch/host/prototypes/listen-test/index.html。

AudioCapture createAudioCapture() => WebAudioCapture();
AudioPlayback createAudioPlayback() => WebAudioPlayback();
ScreenWakeLock createScreenWakeLock() => WebScreenWakeLock();
PageVisibility createPageVisibility() => WebPageVisibility();

/// ⚠️ 必須和後端同步：裝置送 16 kHz、後端送 24 kHz（host spec §12.2）。
const _captureSampleRate = 16000;
const _playbackSampleRate = 24000;

/// 第一段聲音前留一點緩衝，避免開頭被切掉。
const _playbackLead = 0.02;

const _workletName = 'tabletop-pcm-tap';

/// 在 AudioWorklet 裡把浮點樣本轉成 16 位元 PCM，每 512 個樣本（16 kHz 約 32 毫秒）送一次。
const _workletSource =
    '''
class PcmTap extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Int16Array(512); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      for (let i = 0; i < ch.length; i++) {
        const v = Math.max(-1, Math.min(1, ch[i]));
        this.buf[this.n++] = v < 0 ? v * 32768 : v * 32767;
        if (this.n === this.buf.length) {
          const out = this.buf;
          this.port.postMessage(out.buffer, [out.buffer]);
          this.buf = new Int16Array(512);
          this.n = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('$_workletName', PcmTap);
''';

JSObject _options(Map<String, Object> map) => map.jsify()! as JSObject;

// --- 收音 ---

class WebAudioCapture implements AudioCapture {
  _MediaStream? _stream;
  _AudioContext? _context;
  String? _moduleUrl;

  @override
  Future<bool> requestPermission() async {
    if (_stream != null) return true;
    final devices = _navigator.mediaDevices;
    // 不是 HTTPS（或 localhost）時瀏覽器不提供 mediaDevices。
    if (devices == null) return false;
    try {
      _stream = await devices
          .getUserMedia(
            _options({
              'audio': {
                'channelCount': 1,
                'echoCancellation': true,
                'noiseSuppression': true,
                'autoGainControl': true,
              },
            }),
          )
          .toDart;
      return true;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> start(void Function(Uint8List chunk) onChunk) async {
    if (_context != null) return;
    if (!await requestPermission()) {
      throw StateError('沒有麥克風權限');
    }
    final stream = _stream!;
    final context = _AudioContext(_options({'sampleRate': _captureSampleRate}));
    _context = context;
    final url = _moduleUrl ??= _createObjectUrl(
      _Blob(
        [_workletSource.toJS].toJS,
        _options({'type': 'application/javascript'}),
      ),
    );
    await context.audioWorklet.addModule(url).toDart;
    // 等模組載入時被 stop() 了：不要再接上。
    if (!identical(_context, context)) return;

    final tap = _AudioWorkletNode(context, _workletName);
    tap.port.onmessage = ((_MessageEvent event) {
      final data = event.data;
      if (data == null) return;
      onChunk((data as JSArrayBuffer).toDart.asUint8List());
    }).toJS;
    // 音量 0 的出口：讓節點持續運作，又不會把麥克風的聲音播出來。
    final sink = context.createGain()..gain.value = 0;
    context.createMediaStreamSource(stream).connect(tap);
    tap.connect(sink);
    sink.connect(context.destination);
    await context.resume().toDart;
  }

  @override
  Future<void> stop() async {
    final context = _context;
    final stream = _stream;
    _context = null;
    _stream = null;
    if (stream != null) {
      for (final track in stream.getTracks().toDart) {
        track.stop();
      }
    }
    if (context != null) {
      try {
        await context.close().toDart;
      } catch (_) {}
    }
  }
}

// --- 播音 ---

class WebAudioPlayback implements AudioPlayback {
  _AudioContext? _context;
  final _decoder = Pcm16Decoder();

  /// 已排進、還沒播完的聲音，用流水號找。
  final _sources = <int, _AudioBufferSourceNode>{};

  /// 某個流水號播完時要通知的「一段播完」。
  final _segmentEnds = <int, List<void Function()>>{};
  int _sequence = 0;
  int _lastId = 0;
  double _nextTime = 0;

  /// clear() 之後遞增，讓舊的 onended 不再生效。
  int _generation = 0;

  @override
  bool get isUnlocked => _context?.state == 'running';

  @override
  Future<bool> unlock() async {
    try {
      final context = _context ??= _AudioContext(
        _options({'sampleRate': _playbackSampleRate}),
      );
      // resume() 要在點擊的處理流程裡同步呼叫，瀏覽器才會允許出聲。
      await context.resume().toDart;
      return context.state == 'running';
    } catch (_) {
      return false;
    }
  }

  @override
  void enqueue(Uint8List pcm) {
    final context = _context;
    if (context == null) return;
    final samples = _decoder.decode(pcm);
    if (samples.isEmpty) return;

    final buffer = context.createBuffer(1, samples.length, _playbackSampleRate);
    buffer.copyToChannel(samples.toJS, 0);
    final source = context.createBufferSource()..buffer = buffer;
    source.connect(context.destination);
    final startAt = math.max(context.currentTime + _playbackLead, _nextTime);
    source.start(startAt);
    _nextTime = startAt + samples.length / _playbackSampleRate;

    final id = ++_sequence;
    final generation = _generation;
    _sources[id] = source;
    _lastId = id;
    source.onended = ((JSAny? _) {
      if (generation != _generation) return;
      _sources.remove(id);
      // ✅ 這一小段播完：通知在它之前標記的「一段播完」
      final callbacks = _segmentEnds.remove(id);
      if (callbacks == null) return;
      for (final callback in callbacks) {
        callback();
      }
    }).toJS;
  }

  @override
  void markSegmentEnd(void Function() onPlayed) {
    if (!_sources.containsKey(_lastId)) {
      // 沒有還在播的聲音：下一輪事件就算播完。
      final generation = _generation;
      Timer.run(() {
        if (generation == _generation) onPlayed();
      });
      return;
    }
    _segmentEnds.putIfAbsent(_lastId, () => []).add(onPlayed);
  }

  @override
  void clear() {
    _generation++;
    for (final source in _sources.values) {
      source.onended = null;
      try {
        source.stop();
      } catch (_) {}
    }
    _sources.clear();
    _segmentEnds.clear();
    _nextTime = 0;
    _decoder.reset();
  }
}

// --- 螢幕常亮 ---

class WebScreenWakeLock implements ScreenWakeLock {
  _WakeLockSentinel? _sentinel;

  @override
  Future<bool> request() async {
    final api = _navigator.wakeLock;
    if (api == null) return false;
    try {
      _sentinel = await api.request('screen').toDart;
      return true;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> release() async {
    final sentinel = _sentinel;
    _sentinel = null;
    if (sentinel == null) return;
    try {
      await sentinel.release().toDart;
    } catch (_) {}
  }
}

// --- 頁面看不看得見 ---

class WebPageVisibility implements PageVisibility {
  WebPageVisibility() {
    _document.addEventListener(
      'visibilitychange',
      ((JSAny? _) => _changes.add(isVisible)).toJS,
    );
  }

  final _changes = StreamController<bool>.broadcast();

  @override
  bool get isVisible => _document.visibilityState == 'visible';

  @override
  Stream<bool> get changes => _changes.stream;
}

// --- 瀏覽器 API 的最小綁定 ---

@JS('navigator')
external _Navigator get _navigator;

@JS('document')
external _Document get _document;

@JS('URL.createObjectURL')
external String _createObjectUrl(_Blob blob);

extension type _Navigator._(JSObject _) implements JSObject {
  external _MediaDevices? get mediaDevices;
  external _WakeLock? get wakeLock;
}

extension type _Document._(JSObject _) implements JSObject {
  external String get visibilityState;
  external void addEventListener(String type, JSFunction listener);
}

extension type _MediaDevices._(JSObject _) implements JSObject {
  external JSPromise<_MediaStream> getUserMedia(JSObject constraints);
}

extension type _MediaStream._(JSObject _) implements JSObject {
  external JSArray<_MediaStreamTrack> getTracks();
}

extension type _MediaStreamTrack._(JSObject _) implements JSObject {
  external void stop();
}

@JS('Blob')
extension type _Blob._(JSObject _) implements JSObject {
  external factory _Blob(JSArray<JSString> parts, JSObject options);
}

@JS('AudioContext')
extension type _AudioContext._(JSObject _) implements JSObject {
  external factory _AudioContext(JSObject options);
  external double get currentTime;
  external String get state;
  external _AudioNode get destination;
  external _AudioWorklet get audioWorklet;
  external JSPromise<JSAny?> resume();
  external JSPromise<JSAny?> close();
  external _AudioBuffer createBuffer(int channels, int length, num sampleRate);
  external _AudioBufferSourceNode createBufferSource();
  external _GainNode createGain();
  external _AudioNode createMediaStreamSource(_MediaStream stream);
}

extension type _AudioNode._(JSObject _) implements JSObject {
  external JSAny? connect(_AudioNode destination);
}

extension type _GainNode._(JSObject _) implements _AudioNode {
  external _AudioParam get gain;
}

extension type _AudioParam._(JSObject _) implements JSObject {
  external set value(num value);
}

extension type _AudioBuffer._(JSObject _) implements JSObject {
  external void copyToChannel(JSFloat32Array source, int channel);
}

extension type _AudioBufferSourceNode._(JSObject _) implements _AudioNode {
  external set buffer(_AudioBuffer value);
  external set onended(JSFunction? value);
  external void start(num when);
  external void stop();
}

extension type _AudioWorklet._(JSObject _) implements JSObject {
  external JSPromise<JSAny?> addModule(String url);
}

@JS('AudioWorkletNode')
extension type _AudioWorkletNode._(JSObject _) implements _AudioNode {
  external factory _AudioWorkletNode(_AudioContext context, String name);
  external _MessagePort get port;
}

extension type _MessagePort._(JSObject _) implements JSObject {
  external set onmessage(JSFunction? value);
}

extension type _MessageEvent._(JSObject _) implements JSObject {
  external JSAny? get data;
}

extension type _WakeLock._(JSObject _) implements JSObject {
  external JSPromise<_WakeLockSentinel> request(String type);
}

extension type _WakeLockSentinel._(JSObject _) implements JSObject {
  external JSPromise<JSAny?> release();
}
