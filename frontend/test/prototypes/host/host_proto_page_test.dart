import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/router.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/platform/audio_capture.dart';
import 'package:tabletop_hub/core/platform/audio_playback.dart';
import 'package:tabletop_hub/core/platform/page_visibility.dart';
import 'package:tabletop_hub/core/platform/screen_wake_lock.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';
import 'package:tabletop_hub/domains/host/data/hosting_sessions_repository.dart';
import 'package:tabletop_hub/domains/host/state/host_controller.dart';
import 'package:tabletop_hub/prototypes/host/host_proto_page.dart';

import '../../domains/host/support.dart';
import '../../support/fakes.dart';

/// 參考畫面加上它用到的所有 fake（spec §14.4、§14.5）。
class ProtoHarness {
  ProtoHarness({List<HostingSession>? sessions})
    : repo = FakeHostingSessionsRepository(sessions: sessions);

  final FakeHostingSessionsRepository repo;
  final connector = FakeHostStreamConnector();
  final capture = FakeAudioCapture();
  final playback = FakeAudioPlayback();
  final wakeLock = FakeScreenWakeLock();
  final visibility = FakePageVisibility();

  FakeHostStream get stream => connector.current;

  Future<void> pump(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          hostingSessionsRepositoryProvider.overrideWithValue(repo),
          hostStreamConnectorProvider.overrideWithValue(connector),
          audioCaptureProvider.overrideWithValue(capture),
          audioPlaybackProvider.overrideWithValue(playback),
          screenWakeLockProvider.overrideWithValue(wakeLock),
          pageVisibilityProvider.overrideWithValue(visibility),
        ],
        child: const MaterialApp(home: HostProtoPage()),
      ),
    );
    await tester.pumpAndSettle();
  }

  /// 按「開始主持」並讓後端送來一份現況。
  Future<void> start(WidgetTester tester, {HostLiveState? live}) async {
    await tester.tap(find.byKey(const Key('host-start')));
    await tester.pumpAndSettle();
    stream.emit(HostStateMessage(live ?? liveState()));
    await tester.pumpAndSettle();
  }

  Future<void> emit(WidgetTester tester, HostServerMessage message) async {
    stream.emit(message);
    await tester.pumpAndSettle();
  }
}

Iterable<String> routePaths(List<RouteBase> routes) sync* {
  for (final route in routes) {
    if (route is GoRoute) yield route.path;
    yield* routePaths(route.routes);
  }
}

AppConfig config({required bool showPrototypes}) => AppConfig(
  apiBaseUrl: 'http://api.test',
  showPrototypes: showPrototypes,
  devUserEnabled: false,
);

void main() {
  group('路由', () {
    test('/proto/host 只在 SHOW_PROTOTYPES=true 時出現', () {
      final on = createRouter(config(showPrototypes: true));
      final off = createRouter(config(showPrototypes: false));
      expect(routePaths(on.configuration.routes), contains('/proto/host'));
      expect(
        routePaths(off.configuration.routes),
        isNot(contains('/proto/host')),
      );
    });
  });

  group('開主持前', () {
    testWidgets('人數、接話方式、聲線與「開始主持」，預設 7 人、自動接話、男聲', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);

      expect(find.text('語音主持'), findsOneWidget);
      expect(find.byKey(const Key('host-player-count')), findsOneWidget);
      expect(find.text('自動接話'), findsOneWidget);
      expect(find.text('按住說話'), findsOneWidget);
      expect(find.text('主持中也可以切換'), findsOneWidget);
      expect(find.text('男聲'), findsOneWidget);
      expect(find.text('女聲'), findsOneWidget);
      expect(find.text('開始後這場主持不能換'), findsOneWidget);
      expect(find.byKey(const Key('host-start')), findsOneWidget);
      // 沒有保留的主持：不顯示「接著主持」與「重新開始」
      expect(find.byKey(const Key('host-resume')), findsNothing);
      expect(find.byKey(const Key('host-restart')), findsNothing);
    });

    testWidgets('人數用加減鍵調整，只能在 5 到 10', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      Text count() =>
          tester.widget<Text>(find.byKey(const Key('host-player-count')));
      final start = int.parse(count().data!);

      for (var i = 0; i < 8; i++) {
        await tester.tap(find.byKey(const Key('host-player-count-plus')));
        await tester.pump();
      }
      expect(count().data, '10');
      for (var i = 0; i < 8; i++) {
        await tester.tap(find.byKey(const Key('host-player-count-minus')));
        await tester.pump();
      }
      expect(count().data, '5');
      expect(start, inInclusiveRange(5, 10));
    });

    testWidgets('選的接話方式與聲線會帶進開主持的請求', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await tester.tap(find.text('按住說話'));
      await tester.tap(find.text('女聲'));
      await tester.pump();
      await tester.tap(find.byKey(const Key('host-start')));
      await tester.pumpAndSettle();

      final request = h.repo.createRequests.single;
      expect(request.turnTakingMode, TurnTakingMode.pushToTalk);
      expect(request.voice, HostVoice.female);
    });

    testWidgets('有保留的主持：顯示「接著主持（第 2 回合決定出牌）」與「重新開始」', (tester) async {
      final h = ProtoHarness(
        sessions: [
          fakeHostingSession(
            step: HostStep.turn,
            turnNumber: 2,
            phaseNumber: 2,
          ),
        ],
      );
      await h.pump(tester);

      expect(find.text('接著主持（第 2 回合決定出牌）'), findsOneWidget);
      expect(find.byKey(const Key('host-restart')), findsOneWidget);

      await tester.tap(find.byKey(const Key('host-resume')));
      await tester.pumpAndSettle();
      expect(h.repo.connectCalls, hasLength(1));
      expect(h.repo.createRequests, isEmpty);
    });
  });

  group('主持中', () {
    testWidgets('回合內顯示第幾回合與三個階段：已完成、進行中、還沒到', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester, live: liveState(turnNumber: 2, phaseNumber: 2));

      expect(find.text('第 2 回合'), findsOneWidget);
      expect(find.byKey(const Key('host-phase-1-done')), findsOneWidget);
      expect(find.byKey(const Key('host-phase-2-current')), findsOneWidget);
      expect(find.byKey(const Key('host-phase-3-upcoming')), findsOneWidget);
      expect(find.text('傳金幣、放水晶'), findsOneWidget);
      expect(find.text('決定出牌'), findsOneWidget);
      expect(find.text('翻牌結算'), findsOneWidget);
      // 主持中不再顯示開主持前的設定
      expect(find.byKey(const Key('host-start')), findsNothing);
    });

    testWidgets('開場到夜晚顯示節點名稱', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(
        tester,
        live: liveState(
          step: HostStep.night1,
          turnNumber: null,
          phaseNumber: null,
        ),
      );
      expect(find.text('夜晚第一步'), findsOneWidget);
      expect(find.byKey(const Key('host-phase-1-current')), findsNothing);
    });

    testWidgets('查規則時顯示「正在查規則」', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(find.text('正在查規則'), findsNothing);
      await h.emit(tester, HostStateMessage(liveState(lookingUp: true)));
      expect(find.text('正在查規則'), findsOneWidget);
    });

    testWidgets('三顆流程鍵與「結束主持」送出對應的按鍵訊息，結束不再確認', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);

      await tester.tap(find.byKey(const Key('host-previous')));
      await tester.tap(find.byKey(const Key('host-pause')));
      await tester.tap(find.byKey(const Key('host-next')));
      await tester.ensureVisible(find.byKey(const Key('host-end')));
      await tester.tap(find.byKey(const Key('host-end')));
      await tester.pump();

      expect(h.stream.sentJson.map((m) => m['action']).toList(), [
        'previous',
        'pause',
        'next',
        'end',
      ]);
      expect(find.byType(AlertDialog), findsNothing);
    });

    testWidgets('暫停中那顆鍵變成「繼續」，並顯示「主持暫停中」', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(
        find.descendant(
          of: find.byKey(const Key('host-pause')),
          matching: find.text('暫停'),
        ),
        findsOneWidget,
      );

      await h.emit(
        tester,
        HostStateMessage(
          liveState(paused: true, pauseReason: HostPauseReason.command),
        ),
      );

      expect(
        find.descendant(
          of: find.byKey(const Key('host-pause')),
          matching: find.text('繼續'),
        ),
        findsOneWidget,
      );
      expect(find.text('主持暫停中'), findsOneWidget);
      expect(find.text('暫停中也可以問規則'), findsOneWidget);
      await tester.tap(find.byKey(const Key('host-pause')));
      expect(h.stream.sentJson.last['action'], 'resume');
    });

    testWidgets('「可以這樣說」列出八句語音指令，不能點', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);

      expect(find.text('可以這樣說'), findsOneWidget);
      final hints = find.byKey(const Key('host-voice-hints'));
      for (final phrase in [
        '等一下',
        '暫停',
        '繼續',
        '下一步',
        '上一步',
        '結束了',
        '白薔薇贏了',
        '血刃贏了',
      ]) {
        expect(
          find.descendant(of: hints, matching: find.text('「$phrase」')),
          findsOneWidget,
        );
      }
      expect(
        find.descendant(of: hints, matching: find.byType(InkWell)),
        findsNothing,
      );
    });

    testWidgets('接話方式的標籤與「切換」：切到按住說話後出現大按鈕', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(find.byKey(const Key('host-mode-label')), findsOneWidget);
      expect(find.byKey(const Key('host-talk')), findsNothing);

      await tester.tap(find.byKey(const Key('host-switch-mode')));
      // 切換要先關掉舊連線；widget 測試的假時間裡，關連線的等待要給它一點真的時間才會完成
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();
      h.stream.emit(
        HostStateMessage(liveState(turnTakingMode: TurnTakingMode.pushToTalk)),
      );
      await tester.pumpAndSettle();

      expect(
        h.repo.connectCalls.single.turnTakingMode,
        TurnTakingMode.pushToTalk,
      );
      expect(find.byKey(const Key('host-talk')), findsOneWidget);
    });

    testWidgets('按住說話的大按鈕：按下送 down，放開送 up', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await tester.tap(find.text('按住說話'));
      await tester.pump();
      await h.start(
        tester,
        live: liveState(turnTakingMode: TurnTakingMode.pushToTalk),
      );

      await tester.ensureVisible(find.byKey(const Key('host-talk')));
      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('host-talk'))),
        kind: PointerDeviceKind.touch,
      );
      await tester.pump();
      expect(h.stream.sentJson.last, {'type': 'talk', 'state': 'down'});
      await gesture.up();
      await tester.pump();
      expect(h.stream.sentJson.last, {'type': 'talk', 'state': 'up'});
    });

    testWidgets('已結束：顯示「接著主持」與「重新開始」', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      await h.emit(
        tester,
        HostStateMessage(
          liveState(status: HostStatus.ended, turnNumber: 3, phaseNumber: 3),
        ),
      );
      expect(find.text('接著主持（第 3 回合翻牌結算）'), findsOneWidget);
      expect(find.byKey(const Key('host-restart')), findsOneWidget);
    });
  });

  group('提醒（spec §14.5）', () {
    testWidgets('頁面被切走後回來：「點一下繼續」，點了送 resume', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      h.visibility.hide();
      await tester.pumpAndSettle();
      h.visibility.show();
      await tester.pumpAndSettle();

      expect(find.text('點一下繼續'), findsOneWidget);
      await tester.tap(find.text('點一下繼續'));
      await tester.pumpAndSettle();
      expect(h.stream.sentJson.last['action'], 'resume');
    });

    testWidgets('螢幕常亮被拒：一行「請關掉自動鎖定」，主持照常', (tester) async {
      final h = ProtoHarness();
      h.wakeLock.granted = false;
      await h.pump(tester);
      await h.start(tester);
      expect(find.text('請關掉自動鎖定'), findsOneWidget);
      expect(find.byKey(const Key('host-next')), findsOneWidget);
    });

    testWidgets('被別的裝置取代：「已在別的裝置接著主持」', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      await h.emit(
        tester,
        const HostErrorMessage(
          code: HostErrorCodes.sessionTakenOver,
          message: '已在別的裝置接著主持',
        ),
      );
      expect(find.text('已在別的裝置接著主持'), findsOneWidget);
    });

    testWidgets('重新連線中：提醒出現再消失', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      await h.emit(tester, const HostConnectionMessage(ready: false));
      expect(find.text('重新連線中'), findsOneWidget);
      await h.emit(tester, const HostConnectionMessage(ready: true));
      expect(find.text('重新連線中'), findsNothing);
    });

    testWidgets('麥克風被拒絕：「需要麥克風才能主持，請到瀏覽器設定允許」', (tester) async {
      final h = ProtoHarness();
      h.capture.permissionGranted = false;
      await h.pump(tester);
      await tester.tap(find.byKey(const Key('host-start')));
      await tester.pumpAndSettle();
      expect(find.text('需要麥克風才能主持，請到瀏覽器設定允許'), findsOneWidget);
      expect(h.repo.createRequests, isEmpty);
    });

    testWidgets('聲音待啟用：「點一下開啟聲音」', (tester) async {
      final h = ProtoHarness();
      h.playback.unlockResult = false;
      await h.pump(tester);
      await h.start(tester);
      expect(find.text('點一下開啟聲音'), findsOneWidget);
      h.playback.unlockResult = true;
      await tester.tap(find.text('點一下開啟聲音'));
      await tester.pumpAndSettle();
      expect(find.text('點一下開啟聲音'), findsNothing);
    });

    testWidgets('連不上：「主持人暫時連不上，請稍後再試」，附「接著主持」', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      await h.start(tester);
      await h.emit(
        tester,
        const HostErrorMessage(
          code: HostErrorCodes.realtimeUnavailable,
          message: '主持人暫時連不上，請稍後再試',
        ),
      );
      expect(find.text('主持人暫時連不上，請稍後再試'), findsOneWidget);
      expect(find.byKey(const Key('host-resume')), findsOneWidget);
    });

    testWidgets('連線中：載入圖示', (tester) async {
      final h = ProtoHarness();
      await h.pump(tester);
      expect(find.byKey(const Key('host-connecting')), findsNothing);
      expect(hostNoticeText(HostNotice.connecting), isNull);
    });

    test('每一種提醒都有字句（連線中是載入圖示）', () {
      const expected = {
        HostNotice.paused: '主持暫停中',
        HostNotice.tapToResume: '點一下繼續',
        HostNotice.wakeLockDenied: '請關掉自動鎖定',
        HostNotice.takenOver: '已在別的裝置接著主持',
        HostNotice.reconnecting: '重新連線中',
        HostNotice.micDenied: '需要麥克風才能主持，請到瀏覽器設定允許',
        HostNotice.audioLocked: '點一下開啟聲音',
        HostNotice.unavailable: '主持人暫時連不上，請稍後再試',
        HostNotice.forbidden: '這場主持不是你開的',
        HostNotice.invalidPlayerCount: '人數要在 5 到 10 人',
      };
      for (final notice in HostNotice.values) {
        expect(hostNoticeText(notice), expected[notice], reason: '$notice');
      }
    });
  });
}
