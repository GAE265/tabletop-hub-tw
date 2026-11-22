import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/audio_capture.dart';
import 'package:tabletop_hub/core/platform/audio_playback.dart';
import 'package:tabletop_hub/core/platform/page_visibility.dart';
import 'package:tabletop_hub/core/platform/screen_wake_lock.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';
import 'package:tabletop_hub/domains/host/data/hosting_sessions_repository.dart';
import 'package:tabletop_hub/domains/host/state/host_controller.dart';

import '../../support/fakes.dart';

/// 一個控制器加上它用到的所有 fake。
class HostHarness {
  HostHarness({List<HostingSession>? sessions}) {
    repo = FakeHostingSessionsRepository(sessions: sessions, log: log);
    connector = FakeHostStreamConnector(log: log);
    capture = FakeAudioCapture(log: log);
    wakeLock = FakeScreenWakeLock(log: log);
    container = ProviderContainer(
      overrides: [
        hostingSessionsRepositoryProvider.overrideWithValue(repo),
        hostStreamConnectorProvider.overrideWithValue(connector),
        audioCaptureProvider.overrideWithValue(capture),
        audioPlaybackProvider.overrideWithValue(playback),
        screenWakeLockProvider.overrideWithValue(wakeLock),
        pageVisibilityProvider.overrideWithValue(visibility),
      ],
    );
    addTearDown(container.dispose);
    container.listen(hostControllerProvider, (_, _) {});
  }

  final log = <String>[];
  late final FakeHostingSessionsRepository repo;
  late final FakeHostStreamConnector connector;
  late final FakeAudioCapture capture;
  final playback = FakeAudioPlayback();
  late final FakeScreenWakeLock wakeLock;
  final visibility = FakePageVisibility();
  late final ProviderContainer container;

  HostController get controller =>
      container.read(hostControllerProvider.notifier);
  HostState get state => container.read(hostControllerProvider);

  /// 目前的 WebSocket 通道。
  FakeHostStream get stream => connector.current;

  /// 開一場主持並連上。
  Future<void> startHosting({TurnTakingMode mode = TurnTakingMode.auto}) async {
    controller.setTurnTakingMode(mode);
    await controller.start();
  }
}

/// 後端 `state` 訊息的內容：預設在第 1 回合階段 1、進行中。
HostLiveState liveState({
  HostStatus status = HostStatus.active,
  HostStep step = HostStep.turn,
  int? turnNumber = 1,
  int? phaseNumber = 1,
  bool paused = false,
  HostPauseReason? pauseReason,
  bool lookingUp = false,
  TurnTakingMode turnTakingMode = TurnTakingMode.auto,
  HostVoice voice = HostVoice.male,
  HostWinner? winner,
}) => HostLiveState(
  status: status,
  step: step,
  turnNumber: turnNumber,
  phaseNumber: phaseNumber,
  paused: paused,
  pauseReason: pauseReason,
  lookingUp: lookingUp,
  turnTakingMode: turnTakingMode,
  voice: voice,
  winner: winner,
);

Uint8List pcm(List<int> bytes) => Uint8List.fromList(bytes);
