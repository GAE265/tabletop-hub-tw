import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/config/app_config.dart';
import 'host_models.dart';

// ⚠️ 本檔的訊息格式必須和後端 host 的 WebSocket 同步（規格：.scratch/host/spec.md §12）。

/// WebSocket `error` 訊息的錯誤碼（spec §12.4）。
abstract final class HostErrorCodes {
  /// 通行碼不對、過期、用過了。後端送完就關。
  static const ticketInvalid = 'HOST_TICKET_INVALID';

  /// 這場主持不存在或已清掉。後端送完就關。
  static const sessionNotFound = 'HOST_SESSION_NOT_FOUND';

  /// 被別的裝置取代。後端送完就關。
  static const sessionTakenOver = 'HOST_SESSION_TAKEN_OVER';

  /// 連不上語音模型，或重連失敗。後端送完就關。
  static const realtimeUnavailable = 'HOST_REALTIME_UNAVAILABLE';

  /// 裝置送了看不懂的 JSON。連線不關，後端忽略那一則。
  static const badMessage = 'HOST_BAD_MESSAGE';
}

// --- 後端送的訊息 ---

sealed class HostServerMessage {
  const HostServerMessage();
}

/// 二進位訊息：主持人的聲音，24 kHz、單聲道、16 位元 PCM。
class HostAudioMessage extends HostServerMessage {
  const HostAudioMessage(this.pcm);

  final Uint8List pcm;
}

/// `state`：現況。
class HostStateMessage extends HostServerMessage {
  const HostStateMessage(this.state);

  final HostLiveState state;
}

/// `utterance`：主持人的一段話開始送（[start] 為 true）或送完。
class HostUtteranceMessage extends HostServerMessage {
  const HostUtteranceMessage({required this.utteranceId, required this.start});

  final String utteranceId;
  final bool start;

  @override
  bool operator ==(Object other) =>
      other is HostUtteranceMessage &&
      other.utteranceId == utteranceId &&
      other.start == start;

  @override
  int get hashCode => Object.hash(utteranceId, start);
}

/// `flush`：立刻停播並清空；到下一段開始前收到的聲音都丟掉。
class HostFlushMessage extends HostServerMessage {
  const HostFlushMessage();
}

/// `connection`：後端和語音模型的連線。[ready] 為 false 代表重新連線中。
class HostConnectionMessage extends HostServerMessage {
  const HostConnectionMessage({required this.ready});

  final bool ready;

  @override
  bool operator ==(Object other) =>
      other is HostConnectionMessage && other.ready == ready;

  @override
  int get hashCode => ready.hashCode;
}

/// `error`：錯誤碼見 [HostErrorCodes]。
class HostErrorMessage extends HostServerMessage {
  const HostErrorMessage({
    required this.code,
    required this.message,
    this.details = const {},
  });

  final String code;
  final String message;
  final Map<String, dynamic> details;
}

/// 把 WebSocket 收到的一則訊息轉成 [HostServerMessage]。看不懂的回 null，由呼叫端忽略。
HostServerMessage? parseHostServerMessage(Object? raw) {
  if (raw is Uint8List) return HostAudioMessage(raw);
  if (raw is ByteBuffer) return HostAudioMessage(raw.asUint8List());
  if (raw is List<int>) return HostAudioMessage(Uint8List.fromList(raw));
  if (raw is! String) return null;
  try {
    final json = jsonDecode(raw);
    if (json is! Map<String, dynamic>) return null;
    return switch (json['type']) {
      'state' => HostStateMessage(HostLiveState.fromJson(json)),
      'utterance' => HostUtteranceMessage(
        utteranceId: json['utterance_id'] as String,
        start: json['state'] == 'start',
      ),
      'flush' => const HostFlushMessage(),
      'connection' => HostConnectionMessage(ready: json['state'] == 'ready'),
      'error' => _parseError(json['error'] as Map<String, dynamic>),
      _ => null,
    };
  } on FormatException {
    return null;
  } on TypeError {
    return null;
  } on ArgumentError {
    // 列舉值不認得（例如後端多了新的 step）。
    return null;
  }
}

HostErrorMessage _parseError(Map<String, dynamic> error) => HostErrorMessage(
  code: error['code'] as String,
  message: error['message'] as String? ?? '',
  details: (error['details'] as Map?)?.cast<String, dynamic>() ?? const {},
);

// --- 裝置送的訊息 ---

/// 按鍵的動作。
enum HostCommandAction {
  next('next'),
  previous('previous'),
  pause('pause'),
  resume('resume'),
  end('end');

  const HostCommandAction(this.wire);
  final String wire;
}

sealed class HostClientMessage {
  const HostClientMessage();

  Map<String, dynamic> toJson();
}

/// `command`：按鍵，效果和語音指令相同。
class HostCommandMessage extends HostClientMessage {
  const HostCommandMessage(this.action);

  final HostCommandAction action;

  @override
  Map<String, dynamic> toJson() => {'type': 'command', 'action': action.wire};
}

/// `talk`：按住說話的按下（[down] 為 true）與放開。
class HostTalkMessage extends HostClientMessage {
  const HostTalkMessage({required this.down});

  final bool down;

  @override
  Map<String, dynamic> toJson() => {
    'type': 'talk',
    'state': down ? 'down' : 'up',
  };
}

/// `page_hidden`：頁面被切走或鎖屏。
class HostPageHiddenMessage extends HostClientMessage {
  const HostPageHiddenMessage();

  @override
  Map<String, dynamic> toJson() => {'type': 'page_hidden'};
}

/// `playback_done`：這一段在裝置上播完了。
class HostPlaybackDoneMessage extends HostClientMessage {
  const HostPlaybackDoneMessage(this.utteranceId);

  final String utteranceId;

  @override
  Map<String, dynamic> toJson() => {
    'type': 'playback_done',
    'utterance_id': utteranceId,
  };
}

// --- 通道 ---

/// 一條連著的 WebSocket：收送二進位與 JSON 訊息。
abstract interface class HostStream {
  /// 後端送來的訊息；連線關掉時結束。看不懂的訊息不會出現在這裡。
  Stream<HostServerMessage> get messages;

  /// 送玩家的聲音（16 kHz、單聲道、16 位元 PCM）。
  void sendAudio(Uint8List pcm);

  void send(HostClientMessage message);

  /// 關掉連線。可以重複呼叫。
  Future<void> close();
}

/// 用通行碼連上一場主持的 WebSocket。連不上時拋例外。
abstract interface class HostStreamConnector {
  Future<HostStream> connect(String sessionId, String ticket);
}

/// WebSocket 的網址：API 位址換成 ws／wss，通行碼放在網址上
/// （瀏覽器的 WebSocket 不能自訂標頭，spec §12.1）。
/// 沒有指定 API 位址時用頁面的主機，和 dio 打相對路徑的行為一致。
Uri hostStreamUri({
  required String apiBaseUrl,
  required Uri pageBase,
  required String sessionId,
  required String ticket,
}) {
  final base = apiBaseUrl.isEmpty ? pageBase : Uri.parse(apiBaseUrl);
  var basePath = apiBaseUrl.isEmpty ? '' : base.path;
  while (basePath.endsWith('/')) {
    basePath = basePath.substring(0, basePath.length - 1);
  }
  return Uri(
    scheme: base.scheme == 'https' ? 'wss' : 'ws',
    host: base.host,
    port: base.hasPort ? base.port : null,
    path: '$basePath/api/v1/hosting-sessions/$sessionId/stream',
    queryParameters: {'ticket': ticket},
  );
}

class WebSocketHostStreamConnector implements HostStreamConnector {
  const WebSocketHostStreamConnector(this._config);

  final AppConfig _config;

  @override
  Future<HostStream> connect(String sessionId, String ticket) async {
    final channel = WebSocketChannel.connect(
      hostStreamUri(
        apiBaseUrl: _config.apiBaseUrl,
        pageBase: Uri.base,
        sessionId: sessionId,
        ticket: ticket,
      ),
    );
    await channel.ready;
    return _WebSocketHostStream(channel);
  }
}

class _WebSocketHostStream implements HostStream {
  _WebSocketHostStream(this._channel);

  final WebSocketChannel _channel;
  bool _closed = false;

  @override
  late final Stream<HostServerMessage> messages = _channel.stream
      .map(parseHostServerMessage)
      .where((message) => message != null)
      .cast<HostServerMessage>();

  @override
  void sendAudio(Uint8List pcm) {
    if (!_closed) _channel.sink.add(pcm);
  }

  @override
  void send(HostClientMessage message) {
    if (!_closed) _channel.sink.add(jsonEncode(message.toJson()));
  }

  @override
  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    await _channel.sink.close();
  }
}

final hostStreamConnectorProvider = Provider<HostStreamConnector>(
  (ref) => WebSocketHostStreamConnector(ref.watch(appConfigProvider)),
);
