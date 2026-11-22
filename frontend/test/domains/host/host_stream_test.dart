// host 的 WebSocket 訊息（host spec §12）。
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';

void main() {
  group('連線網址', () {
    test('API 位址是 http：換成 ws，通行碼放在網址上', () {
      final uri = hostStreamUri(
        apiBaseUrl: 'http://localhost:8000',
        pageBase: Uri.parse('http://localhost:5173/#/proto/host'),
        sessionId: 'h-1',
        ticket: 't-abc',
      );
      expect(
        uri.toString(),
        'ws://localhost:8000/api/v1/hosting-sessions/h-1/stream?ticket=t-abc',
      );
    });

    test('API 位址是 https 且有路徑：換成 wss，保留路徑', () {
      final uri = hostStreamUri(
        apiBaseUrl: 'https://api.example.com/backend/',
        pageBase: Uri.parse('https://app.example.com/'),
        sessionId: 'h-1',
        ticket: 't 1',
      );
      expect(uri.scheme, 'wss');
      expect(uri.host, 'api.example.com');
      expect(uri.path, '/backend/api/v1/hosting-sessions/h-1/stream');
      expect(uri.queryParameters['ticket'], 't 1');
    });

    test('沒有指定 API 位址：用頁面的主機，不帶頁面的路徑與 #', () {
      final uri = hostStreamUri(
        apiBaseUrl: '',
        pageBase: Uri.parse('https://app.example.com:8443/proto/host#/x'),
        sessionId: 'h-1',
        ticket: 't',
      );
      expect(
        uri.toString(),
        'wss://app.example.com:8443/api/v1/hosting-sessions/h-1/stream?ticket=t',
      );
    });
  });

  group('後端送的訊息', () {
    test('二進位訊息是主持人的聲音', () {
      final bytes = Uint8List.fromList([1, 2, 3, 4]);
      expect(
        parseHostServerMessage(bytes),
        isA<HostAudioMessage>().having((m) => m.pcm, 'pcm', bytes),
      );
      expect(
        parseHostServerMessage(bytes.buffer),
        isA<HostAudioMessage>().having((m) => m.pcm, 'pcm', bytes),
      );
    });

    test('state：解析整份現況', () {
      final message = parseHostServerMessage(
        jsonEncode({
          'type': 'state',
          'status': 'active',
          'step': 'turn',
          'turn_number': 2,
          'phase_number': 1,
          'paused': true,
          'pause_reason': 'page_hidden',
          'looking_up': true,
          'turn_taking_mode': 'auto',
          'voice': 'male',
          'winner': null,
        }),
      );
      final state = (message! as HostStateMessage).state;
      expect(state.status, HostStatus.active);
      expect(state.turnNumber, 2);
      expect(state.phaseNumber, 1);
      expect(state.paused, isTrue);
      expect(state.pauseReason, HostPauseReason.pageHidden);
      expect(state.lookingUp, isTrue);
      expect(state.turnTakingMode, TurnTakingMode.auto);
      expect(state.winner, isNull);
    });

    test('utterance、flush、connection', () {
      expect(
        parseHostServerMessage(
          '{"type": "utterance", "utterance_id": "u-1", "state": "start"}',
        ),
        const HostUtteranceMessage(utteranceId: 'u-1', start: true),
      );
      expect(
        parseHostServerMessage(
          '{"type": "utterance", "utterance_id": "u-1", "state": "end"}',
        ),
        const HostUtteranceMessage(utteranceId: 'u-1', start: false),
      );
      expect(
        parseHostServerMessage('{"type": "flush"}'),
        isA<HostFlushMessage>(),
      );
      expect(
        parseHostServerMessage(
          '{"type": "connection", "state": "reconnecting"}',
        ),
        const HostConnectionMessage(ready: false),
      );
      expect(
        parseHostServerMessage('{"type": "connection", "state": "ready"}'),
        const HostConnectionMessage(ready: true),
      );
    });

    test('error：帶 code、message、details', () {
      final message = parseHostServerMessage(
        jsonEncode({
          'type': 'error',
          'error': {
            'code': 'HOST_SESSION_TAKEN_OVER',
            'message': '已在別的裝置接著主持',
            'details': {'a': 1},
          },
        }),
      );
      expect(
        message,
        isA<HostErrorMessage>()
            .having((m) => m.code, 'code', HostErrorCodes.sessionTakenOver)
            .having((m) => m.details, 'details', {'a': 1}),
      );
    });

    test('看不懂的訊息：回 null，由呼叫端忽略', () {
      expect(parseHostServerMessage('{"type": "transcript"}'), isNull);
      expect(parseHostServerMessage('not json'), isNull);
      expect(parseHostServerMessage('[1, 2]'), isNull);
      expect(parseHostServerMessage(42), isNull);
    });
  });

  group('裝置送的訊息', () {
    test('格式照 spec §12.3', () {
      expect(const HostCommandMessage(HostCommandAction.next).toJson(), {
        'type': 'command',
        'action': 'next',
      });
      expect(const HostCommandMessage(HostCommandAction.previous).toJson(), {
        'type': 'command',
        'action': 'previous',
      });
      expect(const HostTalkMessage(down: true).toJson(), {
        'type': 'talk',
        'state': 'down',
      });
      expect(const HostTalkMessage(down: false).toJson(), {
        'type': 'talk',
        'state': 'up',
      });
      expect(const HostPageHiddenMessage().toJson(), {'type': 'page_hidden'});
      expect(const HostPlaybackDoneMessage('u-1').toJson(), {
        'type': 'playback_done',
        'utterance_id': 'u-1',
      });
    });
  });
}
