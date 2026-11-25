// AI 語音主持的控制器（host spec §14.3、§14.5；情境 §14.7 的 U-01 到 U-20）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';
import 'package:tabletop_hub/domains/host/state/host_controller.dart';
import 'package:tabletop_hub/domains/host/state/host_labels.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  group('開主持前', () {
    test('U-01 沒有保留的主持：載入後不顯示「接著主持」', () async {
      final h = HostHarness();
      await h.controller.load();
      expect(h.state.loading, isFalse);
      expect(h.state.canResume, isFalse);
      expect(h.state.resumeLabel, isNull);
    });

    test('U-02 有一場在第 2 回合階段 2：顯示「接著主持（第 2 回合決定出牌）」', () async {
      final h = HostHarness(
        sessions: [
          fakeHostingSession(
            step: HostStep.turn,
            turnNumber: 2,
            phaseNumber: 2,
          ),
        ],
      );
      await h.controller.load();
      expect(h.state.canResume, isTrue);
      expect(h.state.resumeLabel, '接著主持（第 2 回合決定出牌）');
    });

    test('U-03 開始主持：依序請求麥克風、POST、連線、開始收音、要求常亮', () async {
      final h = HostHarness();
      h.controller.setPlayerCount(8);
      h.controller.setVoice(HostVoice.female);
      await h.controller.start();

      expect(h.log, [
        'mic.request',
        'POST',
        'ws.connect',
        'mic.start',
        'wakeLock.request',
      ]);
      final request = h.repo.createRequests.single;
      expect(request.playerCount, 8);
      expect(request.turnTakingMode, TurnTakingMode.auto);
      expect(request.voice, HostVoice.female);
      expect(h.stream.ticket, 't-1');
      expect(h.playback.unlockCount, 1);
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.state.notices, isNot(contains(HostNotice.audioLocked)));
    });

    test('U-04 麥克風被拒絕：不呼叫 POST，顯示麥克風的提醒', () async {
      final h = HostHarness();
      h.capture.permissionGranted = false;
      await h.controller.start();
      expect(h.repo.createRequests, isEmpty);
      expect(h.connector.streams, isEmpty);
      expect(h.state.notices, contains(HostNotice.micDenied));
    });

    test('U-05 後端回 422：顯示人數的提醒', () async {
      final h = HostHarness();
      h.repo.createError = const ApiException(
        code: 'VALIDATION_ERROR',
        message: '欄位驗證失敗',
        statusCode: 422,
      );
      await h.controller.start();
      expect(h.state.notices, contains(HostNotice.invalidPlayerCount));
      expect(h.connector.streams, isEmpty);
      expect(h.state.connection, isNot(HostConnectionStatus.connected));
    });

    test('U-06 接著主持時後端回 403：顯示沒有權限的提醒', () async {
      final h = HostHarness(sessions: [fakeHostingSession()]);
      await h.controller.load();
      h.repo.connectError = const ApiException(
        code: 'PERMISSION_DENIED',
        message: '沒有權限',
        statusCode: 403,
      );
      await h.controller.resume();
      expect(h.state.notices, contains(HostNotice.forbidden));
      expect(h.connector.streams, isEmpty);
    });

    test('人數只能在 5 到 10 之間', () {
      final h = HostHarness();
      expect(h.state.playerCount, 7);
      h.controller.setPlayerCount(4);
      expect(h.state.playerCount, 5);
      h.controller.setPlayerCount(11);
      expect(h.state.playerCount, 10);
    });

    test('瀏覽器不讓出聲：主持照常開始，顯示「點一下開啟聲音」，點了再試一次', () async {
      final h = HostHarness();
      h.playback.unlockResult = false;
      await h.startHosting();
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.state.notices, contains(HostNotice.audioLocked));

      h.playback.unlockResult = true;
      await h.controller.unlockAudio();
      expect(h.state.notices, isNot(contains(HostNotice.audioLocked)));
    });
  });

  group('主持中', () {
    test('U-07 按下一步：送出 command 的 next', () async {
      final h = HostHarness();
      await h.startHosting();
      h.controller.next();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'next'});
      h.controller.previous();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'previous'});
      h.controller.end();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'end'});
    });

    test('U-08 收到 paused 為真的 state：按鍵變成「繼續」，顯示「主持暫停中」', () async {
      final h = HostHarness();
      await h.startHosting();
      h.controller.togglePause();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'pause'});

      h.stream.emit(
        HostStateMessage(
          liveState(paused: true, pauseReason: HostPauseReason.command),
        ),
      );
      expect(h.state.paused, isTrue);
      expect(pauseButtonLabel(h.state), '繼續');
      expect(h.state.notices, contains(HostNotice.paused));

      h.controller.togglePause();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'resume'});
    });

    test('U-09 收到 looking_up 為真：顯示「正在查規則」', () async {
      final h = HostHarness();
      await h.startHosting();
      expect(h.state.lookingUp, isFalse);
      h.stream.emit(HostStateMessage(liveState(lookingUp: true)));
      expect(h.state.lookingUp, isTrue);
    });

    test('U-10 收到 flush：播音被清空，下一段開始前收到的聲音不播', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-1', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([1, 0])));
      expect(h.playback.queued, hasLength(1));

      h.stream.emit(const HostFlushMessage());
      expect(h.playback.clearCount, 1);
      expect(h.playback.queued, isEmpty);

      // 舊那一段晚到的聲音與結束：丟掉，也不回報播完
      h.stream.emit(HostAudioMessage(pcm([2, 0])));
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-1', start: false),
      );
      h.playback.finishSegments();
      expect(h.playback.queued, isEmpty);
      expect(
        h.stream.sentJson.where((m) => m['type'] == 'playback_done'),
        isEmpty,
      );

      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-2', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([3, 0])));
      expect(h.playback.queued.single, pcm([3, 0]));
    });

    test('U-11 一段播完：送出 playback_done，帶那一段的編號', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-7', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([1, 0, 2, 0])));
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-7', start: false),
      );
      expect(
        h.stream.sentJson.where((m) => m['type'] == 'playback_done'),
        isEmpty,
        reason: '聲音送完不等於播完，要等裝置真的播完',
      );

      h.playback.finishSegments();
      expect(h.stream.sentJson.last, {
        'type': 'playback_done',
        'utterance_id': 'u-7',
      });
    });

    test('U-12 頁面被切走：停止收音與播音，送出 page_hidden', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-1', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([1, 0])));

      h.visibility.hide();
      await pumpEventQueue();
      expect(h.capture.capturing, isFalse);
      expect(h.playback.clearCount, 1);
      expect(h.playback.queued, isEmpty);
      expect(h.stream.sentJson.last, {'type': 'page_hidden'});
    });

    test('U-13 頁面回來：顯示「點一下繼續」，點了之後送 resume、恢復收音', () async {
      final h = HostHarness();
      await h.startHosting();
      h.visibility.hide();
      await pumpEventQueue();
      final sentBefore = h.stream.sentJson.length;

      h.visibility.show();
      await pumpEventQueue();
      expect(h.state.notices, contains(HostNotice.tapToResume));
      expect(h.stream.sentJson.length, sentBefore, reason: '頁面回來時不送訊息');
      expect(h.capture.capturing, isFalse);

      await h.controller.tapToResume();
      expect(h.stream.sentJson.last, {'type': 'command', 'action': 'resume'});
      expect(h.capture.capturing, isTrue);
      expect(h.state.notices, isNot(contains(HostNotice.tapToResume)));
    });

    test('U-14 切換接話方式：舊連線關掉，帶 push_to_talk 拿通行碼，重連後出現按住說話鍵', () async {
      final h = HostHarness();
      await h.startHosting();
      final old = h.stream;
      expect(h.state.showTalkButton, isFalse);

      await h.controller.switchTurnTakingMode();
      expect(old.closed, isTrue);
      expect(h.repo.connectCalls.single.id, 'h-1');
      expect(
        h.repo.connectCalls.single.turnTakingMode,
        TurnTakingMode.pushToTalk,
      );
      expect(h.connector.streams, hasLength(2));
      expect(h.stream.ticket, 't-2');
      expect(h.state.turnTakingMode, TurnTakingMode.pushToTalk);
      expect(h.state.showTalkButton, isTrue);
      expect(h.state.connection, HostConnectionStatus.connected);
    });

    test('U-15 按住說話、正在播音時按下：本機停播，送 talk 的 down', () async {
      final h = HostHarness();
      await h.startHosting(mode: TurnTakingMode.pushToTalk);
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-1', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([1, 0])));

      h.controller.talkDown();
      expect(h.playback.clearCount, 1);
      expect(h.playback.queued, isEmpty);
      expect(h.stream.sentJson.last, {'type': 'talk', 'state': 'down'});
      expect(h.state.talkHeld, isTrue);

      // 按下之後，舊那一段晚到的聲音不播
      h.stream.emit(HostAudioMessage(pcm([2, 0])));
      expect(h.playback.queued, isEmpty);

      h.controller.talkUp();
      expect(h.stream.sentJson.last, {'type': 'talk', 'state': 'up'});
      expect(h.state.talkHeld, isFalse);
    });

    test('按住說話：只有按著的時候才送聲音；自動接話一直送', () async {
      final ptt = HostHarness();
      await ptt.startHosting(mode: TurnTakingMode.pushToTalk);
      ptt.capture.emit(pcm([1, 0]));
      expect(ptt.stream.sentAudio, isEmpty);
      ptt.controller.talkDown();
      ptt.capture.emit(pcm([2, 0]));
      ptt.controller.talkUp();
      ptt.capture.emit(pcm([3, 0]));
      expect(ptt.stream.sentAudio, [
        pcm([2, 0]),
      ]);

      final auto = HostHarness();
      await auto.startHosting();
      auto.capture.emit(pcm([4, 0]));
      expect(auto.stream.sentAudio, [
        pcm([4, 0]),
      ]);
    });

    test('U-16 收到 HOST_SESSION_TAKEN_OVER：顯示「已在別的裝置接著主持」，停止收音', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostErrorMessage(
          code: HostErrorCodes.sessionTakenOver,
          message: '已在別的裝置接著主持',
        ),
      );
      await pumpEventQueue();
      expect(h.state.notices, contains(HostNotice.takenOver));
      expect(h.capture.capturing, isFalse);
      expect(h.wakeLock.held, isFalse);
      expect(h.state.connection, HostConnectionStatus.closed);
    });

    test('U-17 收到重新連線中、再收到已連上：提醒出現再消失', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(const HostConnectionMessage(ready: false));
      expect(h.state.notices, contains(HostNotice.reconnecting));
      h.stream.emit(const HostConnectionMessage(ready: true));
      expect(h.state.notices, isNot(contains(HostNotice.reconnecting)));
      expect(h.state.connection, HostConnectionStatus.connected);
    });

    test('U-18 收到 HOST_REALTIME_UNAVAILABLE：顯示連不上，有「接著主持」', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostErrorMessage(
          code: HostErrorCodes.realtimeUnavailable,
          message: '連不上語音模型',
        ),
      );
      await pumpEventQueue();
      expect(h.state.notices, contains(HostNotice.unavailable));
      expect(h.state.canResume, isTrue);
      expect(h.capture.capturing, isFalse);

      // 按「接著主持」：用同一場主持拿通行碼再連上
      await h.controller.resume();
      expect(h.repo.connectCalls.single.id, 'h-1');
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.state.notices, isNot(contains(HostNotice.unavailable)));
    });

    test('U-19 螢幕常亮被拒：顯示一行提醒，主持照常', () async {
      final h = HostHarness();
      h.wakeLock.granted = false;
      await h.startHosting();
      expect(h.state.notices, contains(HostNotice.wakeLockDenied));
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.capture.capturing, isTrue);
    });

    test('已結束就不顯示流程鍵與「結束主持」；還沒連上也不顯示', () async {
      final h = HostHarness();
      expect(h.state.showFlowControls, isFalse);
      await h.startHosting();
      h.stream.emit(HostStateMessage(liveState()));
      await pumpEventQueue();
      expect(h.state.showFlowControls, isTrue);

      h.stream.emit(HostStateMessage(liveState(status: HostStatus.ended)));
      await pumpEventQueue();
      expect(h.state.showFlowControls, isFalse);
      // 接著主持：狀態變回進行中，流程鍵回來
      h.stream.emit(HostStateMessage(liveState()));
      await pumpEventQueue();
      expect(h.state.showFlowControls, isTrue);
    });

    test('U-20 收到 status 是 ended：顯示「接著主持」與「重新開始」', () async {
      final h = HostHarness();
      await h.startHosting();
      expect(h.state.canResume, isFalse);
      h.stream.emit(
        HostStateMessage(
          liveState(
            status: HostStatus.ended,
            step: HostStep.ended,
            turnNumber: 3,
            phaseNumber: 2,
          ),
        ),
      );
      expect(h.state.canResume, isTrue);
      expect(h.state.canRestart, isTrue);
      expect(h.state.resumeLabel, '接著主持（第 3 回合決定出牌）');
    });

    test('後端忽略的錯誤 HOST_BAD_MESSAGE：連線照常', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostErrorMessage(code: HostErrorCodes.badMessage, message: '看不懂'),
      );
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.state.problem, isNull);
    });

    test('後端無預警關掉連線：停止收音，顯示連不上', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.serverClose();
      await pumpEventQueue();
      expect(h.state.connection, HostConnectionStatus.closed);
      expect(h.state.notices, contains(HostNotice.unavailable));
      expect(h.capture.capturing, isFalse);
    });
  });

  group('按「結束主持」', () {
    /// 開一場主持、按「結束主持」，後端回已結束。
    Future<HostHarness> endedByButton() async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(HostStateMessage(liveState(turnNumber: 3, phaseNumber: 2)));
      h.controller.end();
      h.stream.emit(
        HostStateMessage(
          liveState(
            status: HostStatus.ended,
            step: HostStep.ended,
            turnNumber: 3,
            phaseNumber: 2,
          ),
        ),
      );
      await pumpEventQueue();
      return h;
    }

    /// 主持人的一段話：開始、一小段聲音、結束。
    void speak(HostHarness h, String id) {
      h.stream.emit(HostUtteranceMessage(utteranceId: id, start: true));
      h.stream.emit(HostAudioMessage(pcm([1, 0])));
      h.stream.emit(HostUtteranceMessage(utteranceId: id, start: false));
    }

    test('後端回已結束：回到開主持前，停止收音、放開常亮，連線留著唸結束台詞', () async {
      final h = await endedByButton();
      expect(h.state.isLive, isFalse);
      expect(h.state.connection, HostConnectionStatus.idle);
      expect(h.capture.capturing, isFalse);
      expect(h.wakeLock.held, isFalse);
      expect(h.stream.closed, isFalse);
      expect(h.state.notices, isEmpty);
    });

    test('結束台詞播完：回報播完、關連線，不顯示連不上', () async {
      final h = await endedByButton();
      speak(h, 'u-end');
      expect(h.playback.queued, hasLength(1));
      expect(h.stream.closed, isFalse);

      h.playback.finishSegments();
      await pumpEventQueue();
      expect(h.stream.sentJson.last, {
        'type': 'playback_done',
        'utterance_id': 'u-end',
      });
      expect(h.stream.closed, isTrue);
      expect(h.state.connection, HostConnectionStatus.idle);
      expect(h.state.problem, isNull);
    });

    test('按之前就在說的那一段不算結束台詞：不再播，也不關連線', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-old', start: true),
      );
      h.stream.emit(HostAudioMessage(pcm([1, 0])));
      h.controller.end();
      h.stream.emit(HostStateMessage(liveState(status: HostStatus.ended)));
      expect(h.playback.queued, isEmpty);

      h.stream.emit(HostAudioMessage(pcm([2, 0])));
      h.stream.emit(
        const HostUtteranceMessage(utteranceId: 'u-old', start: false),
      );
      h.playback.finishSegments();
      await pumpEventQueue();
      expect(h.playback.queued, isEmpty);
      expect(h.stream.closed, isFalse);

      speak(h, 'u-end');
      h.playback.finishSegments();
      await pumpEventQueue();
      expect(h.stream.closed, isTrue);
    });

    test('連按兩次只送一次結束', () async {
      final h = HostHarness();
      await h.startHosting();
      h.controller.end();
      h.controller.end();
      expect(h.stream.sentJson.where((m) => m['action'] == 'end').length, 1);
    });

    test('回到開主持前之後，後端斷線或重連語音模型都不影響畫面', () async {
      final h = await endedByButton();
      h.stream.emit(const HostConnectionMessage(ready: false));
      expect(h.state.isLive, isFalse);
      h.stream.emit(const HostConnectionMessage(ready: true));
      expect(h.state.isLive, isFalse);

      h.stream.serverClose();
      await pumpEventQueue();
      expect(h.state.connection, HostConnectionStatus.idle);
      expect(h.state.notices, isEmpty);
    });

    test('結束台詞還在唸就按「接著主持」：停播、關舊連線、開新連線', () async {
      final h = await endedByButton();
      expect(h.state.resumeLabel, '接著主持（第 3 回合決定出牌）');
      final old = h.stream;
      speak(h, 'u-end');
      await h.controller.resume();

      expect(old.closed, isTrue);
      expect(h.playback.queued, isEmpty);
      expect(h.connector.streams, hasLength(2));
      expect(h.stream.closed, isFalse);
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.capture.capturing, isTrue);
      expect(h.wakeLock.held, isTrue);
    });

    test('結束台詞還在唸就按「重新開始」：停播、關舊連線、開新的一場', () async {
      final h = await endedByButton();
      final old = h.stream;
      speak(h, 'u-end');
      await h.controller.restart();

      expect(old.closed, isTrue);
      expect(h.playback.queued, isEmpty);
      expect(h.repo.createRequests, hasLength(2));
      expect(h.state.connection, HostConnectionStatus.connected);
      expect(h.capture.capturing, isTrue);
    });

    test('用說的結束：照舊留在主持中，繼續收音', () async {
      final h = HostHarness();
      await h.startHosting();
      h.stream.emit(HostStateMessage(liveState(status: HostStatus.ended)));
      speak(h, 'u-end');
      h.playback.finishSegments();
      await pumpEventQueue();
      expect(h.state.isLive, isTrue);
      expect(h.capture.capturing, isTrue);
      expect(h.stream.closed, isFalse);
    });
  });

  group('進度文字', () {
    test('開場到夜晚顯示節點名稱，回合內顯示第幾回合與階段', () {
      expect(hostProgressLabel(HostStep.opening, null, null), '開場');
      expect(hostProgressLabel(HostStep.setup, null, null), '開局準備');
      expect(hostProgressLabel(HostStep.night1, null, null), '夜晚第一步');
      expect(hostProgressLabel(HostStep.night2, null, null), '夜晚第二步');
      expect(hostProgressLabel(HostStep.turn, 1, 1), '第 1 回合傳金幣、放水晶');
      expect(hostProgressLabel(HostStep.turn, 4, 3), '第 4 回合翻牌結算');
      expect(hostProgressLabel(HostStep.ended, null, null), '結束');
    });
  });
}
