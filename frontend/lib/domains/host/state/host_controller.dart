import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/platform/audio_capture.dart';
import '../../../core/platform/audio_playback.dart';
import '../../../core/platform/page_visibility.dart';
import '../../../core/platform/screen_wake_lock.dart';
import '../data/host_models.dart';
import '../data/host_stream.dart';
import '../data/hosting_sessions_repository.dart';
import 'host_labels.dart';

/// 人數範圍（spec §2.1）。
const hostMinPlayers = 5;
const hostMaxPlayers = 10;

/// 按「結束主持」後最多等這麼久：等後端回已結束、等結束台詞播完，各算一次。
const hostEndTimeout = Duration(seconds: 10);

/// 和後端的 WebSocket 連線狀態。
enum HostConnectionStatus {
  /// 還沒開始主持；或按了「結束主持」，回到開主持前的畫面。
  idle,

  /// 正在開主持、拿通行碼或連 WebSocket。
  connecting,
  connected,

  /// 後端和語音模型的連線斷了，正在重連（WebSocket 本身還連著）。
  reconnecting,

  /// 連線已關掉（出錯或被取代）。
  closed,
}

/// 擋住主持、要玩家處理的問題。同一時間只會有一個。
enum HostProblem {
  micDenied,
  invalidPlayerCount,
  forbidden,
  unavailable,
  takenOver,
}

/// 頁面要顯示的提醒（spec §14.5）。字句由畫面決定（ticket 10），這裡只給狀況。
enum HostNotice {
  /// 「主持暫停中」，附「暫停中也可以問規則」。
  paused,

  /// 頁面被切走後回來：「點一下繼續」。
  tapToResume,

  /// 螢幕常亮被拒：一行「請關掉自動鎖定」，不擋主持。
  wakeLockDenied,

  /// 「已在別的裝置接著主持」。
  takenOver,

  /// 「重新連線中」。
  reconnecting,

  /// 「需要麥克風才能主持，請到瀏覽器設定允許」。
  micDenied,

  /// 「點一下開啟聲音」。
  audioLocked,

  /// 「主持人暫時連不上，請稍後再試」，附「接著主持」。
  unavailable,

  /// 「這場主持不是你開的」。
  forbidden,

  /// 「人數要在 5 到 10 人」。
  invalidPlayerCount,

  /// 連線中：載入圖示。
  connecting,
}

class HostState {
  const HostState({
    this.playerCount = 7,
    this.turnTakingMode = TurnTakingMode.auto,
    this.voice = HostVoice.male,
    this.loading = false,
    this.resumable,
    this.sessionId,
    this.connection = HostConnectionStatus.idle,
    this.live,
    this.talkHeld = false,
    this.problem,
    this.wakeLockDenied = false,
    this.needsTapToResume = false,
    this.audioLocked = false,
  });

  final int playerCount;
  final TurnTakingMode turnTakingMode;

  /// 開始後這場主持不能換。
  final HostVoice voice;

  /// 正在載入有沒有可以接著的主持。
  final bool loading;

  /// 載入時找到、或剛開的那場主持（已結束的也算）。
  final HostingSession? resumable;

  /// 目前這場主持的 id。
  final String? sessionId;
  final HostConnectionStatus connection;

  /// 最近一則 `state` 訊息的內容；還沒連上是 null。
  final HostLiveState? live;

  /// 按住說話鍵是不是按著。
  final bool talkHeld;
  final HostProblem? problem;
  final bool wakeLockDenied;

  /// 頁面被切走過，要玩家點一下才繼續。
  final bool needsTapToResume;

  /// 瀏覽器還不讓出聲，要玩家點一下。
  final bool audioLocked;

  /// WebSocket 連著（含後端正在重連語音模型）。
  bool get isLive =>
      connection == HostConnectionStatus.connected ||
      connection == HostConnectionStatus.reconnecting;

  bool get paused => live?.paused ?? false;

  /// 「正在查規則」。
  bool get lookingUp => live?.lookingUp ?? false;

  bool get ended => live?.status == HostStatus.ended;

  /// 顯示流程鍵（上一步、暫停或繼續、下一步）與「結束主持」：連著而且這一局還沒結束。
  /// 已結束後這些鍵按了不會動（spec §3.3），所以收起來；主持人仍連著，可以照常問規則。
  bool get showFlowControls => isLive && live != null && !ended;

  /// 只在按住說話時出現按住說話鍵。
  bool get showTalkButton =>
      isLive && turnTakingMode == TurnTakingMode.pushToTalk;

  String? get _resumeTarget => sessionId ?? resumable?.id;

  /// 顯示「接著主持」：有保留的主持，而且沒在連線中；或連著但已結束。
  bool get canResume {
    if (_resumeTarget == null) return false;
    if (connection == HostConnectionStatus.connecting) return false;
    return !isLive || ended;
  }

  /// 顯示「重新開始」：條件和「接著主持」相同。
  bool get canRestart => canResume;

  /// 「接著主持（第 N 回合某階段）」；不能接著時是 null。
  String? get resumeLabel {
    if (!canResume) return null;
    final current = live;
    final progress = current != null
        ? hostProgressLabel(
            current.step,
            current.turnNumber,
            current.phaseNumber,
          )
        : resumable != null
        ? hostProgressLabel(
            resumable!.step,
            resumable!.turnNumber,
            resumable!.phaseNumber,
          )
        : null;
    return progress == null ? '接著主持' : '接著主持（$progress）';
  }

  /// 目前要顯示的提醒，可能同時有好幾個。
  List<HostNotice> get notices => [
    if (connection == HostConnectionStatus.connecting) HostNotice.connecting,
    if (connection == HostConnectionStatus.reconnecting)
      HostNotice.reconnecting,
    if (needsTapToResume)
      HostNotice.tapToResume
    else if (isLive && paused)
      HostNotice.paused,
    if (audioLocked) HostNotice.audioLocked,
    if (wakeLockDenied && isLive) HostNotice.wakeLockDenied,
    if (problem != null) _problemNotices[problem]!,
  ];

  HostState copyWith({
    int? playerCount,
    TurnTakingMode? turnTakingMode,
    HostVoice? voice,
    bool? loading,
    HostingSession? Function()? resumable,
    String? Function()? sessionId,
    HostConnectionStatus? connection,
    HostLiveState? Function()? live,
    bool? talkHeld,
    HostProblem? Function()? problem,
    bool? wakeLockDenied,
    bool? needsTapToResume,
    bool? audioLocked,
  }) => HostState(
    playerCount: playerCount ?? this.playerCount,
    turnTakingMode: turnTakingMode ?? this.turnTakingMode,
    voice: voice ?? this.voice,
    loading: loading ?? this.loading,
    resumable: resumable == null ? this.resumable : resumable(),
    sessionId: sessionId == null ? this.sessionId : sessionId(),
    connection: connection ?? this.connection,
    live: live == null ? this.live : live(),
    talkHeld: talkHeld ?? this.talkHeld,
    problem: problem == null ? this.problem : problem(),
    wakeLockDenied: wakeLockDenied ?? this.wakeLockDenied,
    needsTapToResume: needsTapToResume ?? this.needsTapToResume,
    audioLocked: audioLocked ?? this.audioLocked,
  );
}

const _problemNotices = {
  HostProblem.micDenied: HostNotice.micDenied,
  HostProblem.invalidPlayerCount: HostNotice.invalidPlayerCount,
  HostProblem.forbidden: HostNotice.forbidden,
  HostProblem.unavailable: HostNotice.unavailable,
  HostProblem.takenOver: HostNotice.takenOver,
};

/// 語音主持頁面的控制器，參考畫面與正式頁面共用（spec §14.3）。
///
/// 離開頁面就停止收音、關掉連線；這場主持仍保留在後端，可以接著主持。
class HostController extends Notifier<HostState> {
  HostStream? _stream;
  StreamSubscription<HostServerMessage>? _streamSubscription;
  StreamSubscription<bool>? _visibilitySubscription;
  bool _capturing = false;
  bool _micGranted = false;

  /// 收到 `flush` 或本機按下說話後為 true：到下一段開始前收到的聲音都丟掉。
  bool _dropAudio = false;
  String? _utteranceId;

  /// 按了「結束主持」之後的等待；有值代表正在結束。
  Timer? _endTimer;

  /// 已經回到開主持前的畫面，連線只留著唸結束台詞。
  bool _leaving = false;

  /// 結束台詞那一段；按「結束主持」之前就在說的不算。
  String? _closingUtteranceId;

  HostingSessionsRepository get _repo =>
      ref.read(hostingSessionsRepositoryProvider);
  HostStreamConnector get _connector => ref.read(hostStreamConnectorProvider);

  // 收音、播音、常亮在 build 時先取得：離開頁面（onDispose）時要用來收尾，那時不能再讀 provider。
  late AudioCapture _capture;
  late AudioPlayback _playback;
  late ScreenWakeLock _wakeLock;

  @override
  HostState build() {
    _capture = ref.read(audioCaptureProvider);
    _playback = ref.read(audioPlaybackProvider);
    _wakeLock = ref.read(screenWakeLockProvider);
    _visibilitySubscription = ref
        .read(pageVisibilityProvider)
        .changes
        .listen(_onVisibilityChanged);
    ref.onDispose(_dispose);
    return const HostState();
  }

  // --- 設定 ---

  void setPlayerCount(int count) => state = state.copyWith(
    playerCount: count.clamp(hostMinPlayers, hostMaxPlayers),
  );

  void setTurnTakingMode(TurnTakingMode mode) {
    if (state.isLive) return; // 主持中用 switchTurnTakingMode
    state = state.copyWith(turnTakingMode: mode);
  }

  void setVoice(HostVoice voice) {
    if (state.isLive) return; // 開始後這場主持不能換
    state = state.copyWith(voice: voice);
  }

  // --- 開始、接著、重新開始 ---

  /// 看有沒有可以接著的主持。
  Future<void> load() async {
    state = state.copyWith(loading: true);
    try {
      final sessions = await _repo.list();
      if (!ref.mounted) return;
      state = state.copyWith(
        loading: false,
        resumable: () => sessions.isEmpty ? null : sessions.first,
      );
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(loading: false, problem: () => _problemFor(error));
    }
  }

  /// 開始主持：請求麥克風與出聲 → POST → 連 WebSocket → 開始收音 → 要求螢幕常亮。
  Future<void> start() async {
    if (state.connection == HostConnectionStatus.connecting) return;
    _dropClosingLine();
    if (!await _prepareDevice()) return;
    await _closeStream();
    state = state.copyWith(
      connection: HostConnectionStatus.connecting,
      live: () => null,
    );
    final HostingSessionAccess access;
    try {
      access = await _repo.create(
        CreateHostingSessionRequest(
          playerCount: state.playerCount,
          turnTakingMode: state.turnTakingMode,
          voice: state.voice,
        ),
      );
    } catch (error) {
      if (!ref.mounted) return;
      state = state.copyWith(
        connection: HostConnectionStatus.idle,
        problem: () => _problemFor(error),
      );
      return;
    }
    await _open(access);
  }

  /// 重新開始：和開始主持相同，舊的那場由後端清掉。
  Future<void> restart() => start();

  /// 接著主持：拿通行碼 → 連 WebSocket。
  Future<void> resume() async {
    final id = state.sessionId ?? state.resumable?.id;
    if (id == null || state.connection == HostConnectionStatus.connecting) {
      return;
    }
    _dropClosingLine();
    if (!await _prepareDevice()) return;
    await _reconnect(id);
  }

  /// 主持中切換接話方式：關掉連線 → 帶新的接話方式拿通行碼 → 重連。
  Future<void> switchTurnTakingMode() async {
    final id = state.sessionId;
    if (id == null || !state.isLive) return;
    final next = state.turnTakingMode == TurnTakingMode.auto
        ? TurnTakingMode.pushToTalk
        : TurnTakingMode.auto;
    await _reconnect(id, turnTakingMode: next);
  }

  // --- 按鍵 ---

  void next() => _sendCommand(HostCommandAction.next);

  void previous() => _sendCommand(HostCommandAction.previous);

  /// 暫停中送「繼續」，否則送「暫停」。
  void togglePause() => _sendCommand(
    state.paused ? HostCommandAction.resume : HostCommandAction.pause,
  );

  /// 結束主持，不再確認（spec §3.3）：送「結束」→ 後端回已結束 → 回到開主持前的畫面
  /// → 結束台詞播完才關連線。太早關，後端會丟掉還沒處理的「結束」，台詞也會被切斷。
  void end() {
    if (!state.isLive || _endTimer != null) return;
    _sendCommand(HostCommandAction.end);
    _endTimer = Timer(hostEndTimeout, _finishEnding);
  }

  /// 按住說話：按下。本機先停播，不等後端的 `flush`。
  void talkDown() {
    if (!state.showTalkButton || state.talkHeld) return;
    _stopPlayback();
    _stream?.send(const HostTalkMessage(down: true));
    state = state.copyWith(talkHeld: true);
  }

  /// 按住說話：放開，主持人才回答。
  void talkUp() {
    if (!state.talkHeld) return;
    _stream?.send(const HostTalkMessage(down: false));
    state = state.copyWith(talkHeld: false);
  }

  /// 頁面被切走後回來，玩家點「點一下繼續」：送「繼續」並恢復收音。
  Future<void> tapToResume() async {
    if (!state.needsTapToResume || !state.isLive) return;
    final unlocked = _playback.isUnlocked || await _playback.unlock();
    _sendCommand(HostCommandAction.resume);
    state = state.copyWith(needsTapToResume: false, audioLocked: !unlocked);
    await _startCapture();
    // 頁面被切走時系統會放開常亮，回來要再要求一次。
    await _requestWakeLock();
  }

  /// 玩家點「點一下開啟聲音」。
  Future<void> unlockAudio() async {
    final unlocked = await _playback.unlock();
    if (!ref.mounted) return;
    state = state.copyWith(audioLocked: !unlocked);
  }

  // --- 內部流程 ---

  /// 請求麥克風與出聲。麥克風被拒就停下來；出聲被拒只提醒，不擋主持。
  Future<bool> _prepareDevice() async {
    state = state.copyWith(problem: () => null);
    // 先同步叫出聲，瀏覽器才認得這是玩家點擊造成的（麥克風的詢問可能拖很久）。
    final unlocking = _playback.isUnlocked
        ? Future.value(true)
        : _playback.unlock();
    final granted = _micGranted || await _capture.requestPermission();
    final unlocked = await unlocking;
    if (!ref.mounted) return false;
    if (!granted) {
      state = state.copyWith(problem: () => HostProblem.micDenied);
      return false;
    }
    _micGranted = true;
    state = state.copyWith(audioLocked: !unlocked);
    return true;
  }

  Future<void> _reconnect(String id, {TurnTakingMode? turnTakingMode}) async {
    await _closeStream();
    _stopPlayback();
    state = state.copyWith(
      connection: HostConnectionStatus.connecting,
      talkHeld: false,
      problem: () => null,
    );
    final HostingSessionAccess access;
    try {
      access = await _repo.connect(id, turnTakingMode: turnTakingMode);
    } catch (error) {
      if (!ref.mounted) return;
      final gone =
          error is ApiException && error.code == HostErrorCodes.sessionNotFound;
      await _stopCapture();
      state = state.copyWith(
        connection: HostConnectionStatus.closed,
        problem: () => gone ? null : _problemFor(error),
        // 這場主持已被清掉：不再顯示「接著主持」。
        sessionId: gone ? () => null : null,
        resumable: gone ? () => null : null,
        live: gone ? () => null : null,
      );
      return;
    }
    await _open(access);
  }

  /// 拿到通行碼之後：連 WebSocket → 開始收音 → 要求螢幕常亮。
  Future<void> _open(HostingSessionAccess access) async {
    final session = access.session;
    state = state.copyWith(
      sessionId: () => session.id,
      resumable: () => session,
      turnTakingMode: session.turnTakingMode,
      voice: session.voice,
      playerCount: session.playerCount,
      needsTapToResume: false,
    );
    final HostStream stream;
    try {
      stream = await _connector.connect(session.id, access.connection.ticket);
    } catch (_) {
      if (!ref.mounted) return;
      await _stopCapture();
      state = state.copyWith(
        connection: HostConnectionStatus.closed,
        problem: () => HostProblem.unavailable,
      );
      return;
    }
    if (!ref.mounted) {
      unawaited(stream.close());
      return;
    }
    _stream = stream;
    _dropAudio = false;
    _utteranceId = null;
    _streamSubscription = stream.messages.listen(
      _onMessage,
      onDone: () => _onStreamDone(stream),
      onError: (Object _) {},
    );
    state = state.copyWith(connection: HostConnectionStatus.connected);
    await _startCapture();
    await _requestWakeLock();
  }

  void _onMessage(HostServerMessage message) {
    switch (message) {
      // 已經回到開主持前的畫面：現況與重連都不再影響畫面
      case HostStateMessage() || HostConnectionMessage() when _leaving:
        return;
      case HostStateMessage(:final state):
        this.state = this.state.copyWith(
          live: () => state,
          turnTakingMode: state.turnTakingMode,
          voice: state.voice,
        );
        if (_endTimer != null && this.state.ended) _leaveHosting();
      case HostUtteranceMessage(:final utteranceId, start: true):
        _utteranceId = utteranceId;
        _dropAudio = false;
        if (_leaving) _closingUtteranceId ??= utteranceId;
      case HostUtteranceMessage(:final utteranceId, start: false):
        if (_dropAudio || utteranceId != _utteranceId) return;
        final stream = _stream;
        _playback.markSegmentEnd(() {
          // ✅ 這一段在裝置上播完：回報給後端，後端才會自動往下走
          if (identical(stream, _stream)) {
            stream?.send(HostPlaybackDoneMessage(utteranceId));
            if (utteranceId == _closingUtteranceId) _finishEnding();
          }
        });
      case HostAudioMessage(:final pcm):
        if (!_dropAudio) _playback.enqueue(pcm);
      case HostFlushMessage():
        _stopPlayback();
      case HostConnectionMessage(:final ready):
        state = state.copyWith(
          connection: ready
              ? HostConnectionStatus.connected
              : HostConnectionStatus.reconnecting,
        );
      case HostErrorMessage(:final code):
        _onError(code);
    }
  }

  void _onError(String code) {
    switch (code) {
      case HostErrorCodes.badMessage:
        return; // 後端忽略那一則，連線照常
      case HostErrorCodes.sessionTakenOver:
        unawaited(_shutDown(HostProblem.takenOver));
      default:
        unawaited(_shutDown(HostProblem.unavailable));
    }
  }

  void _onStreamDone(HostStream stream) {
    // 自己關掉的（切換接話方式、離開頁面）不算斷線。
    if (!identical(stream, _stream)) return;
    unawaited(_shutDown(state.problem ?? HostProblem.unavailable));
  }

  /// 連線出錯或被取代：停止收音與播音，放開常亮，關掉連線。
  Future<void> _shutDown(HostProblem problem) async {
    if (_leaving) {
      // 已經回到開主持前的畫面：只是唸不完結束台詞，不用提醒
      _finishEnding();
      return;
    }
    _stopPlayback();
    state = state.copyWith(
      connection: HostConnectionStatus.closed,
      problem: () => problem,
      talkHeld: false,
      needsTapToResume: false,
    );
    await _closeStream();
    await _stopCapture();
    await _wakeLock.release();
  }

  /// 回到開主持前的畫面：停止收音、放開常亮；連線留著唸結束台詞。
  void _leaveHosting() {
    _leaving = true;
    _endTimer?.cancel();
    _endTimer = Timer(hostEndTimeout, _finishEnding);
    // 還在說的那一段不播了，接下來只唸結束台詞
    _stopPlayback();
    state = state.copyWith(
      connection: HostConnectionStatus.idle,
      talkHeld: false,
      problem: () => null,
      needsTapToResume: false,
      audioLocked: false,
    );
    unawaited(_stopCapture());
    unawaited(_wakeLock.release());
  }

  /// ✅ 結束台詞播完、等太久，或連線斷了：關連線。
  void _finishEnding() {
    if (!_leaving) _leaveHosting(); // 後端沒有回應
    _dropClosingLine();
  }

  /// 還在唸結束台詞就停播、關連線；沒有在唸就不做事。
  void _dropClosingLine() {
    if (!_leaving) return;
    _stopPlayback();
    unawaited(_closeStream());
  }

  void _onVisibilityChanged(bool visible) {
    if (!state.isLive) return;
    if (visible) return; // 回來時不送訊息，等玩家點一下（spec §12.3）
    unawaited(_stopCapture());
    _stopPlayback();
    _stream?.send(const HostPageHiddenMessage());
    state = state.copyWith(needsTapToResume: true, talkHeld: false);
  }

  void _onChunk(Uint8List chunk) {
    // 按住說話時只送按著的那段；自動接話一直送。
    if (state.turnTakingMode == TurnTakingMode.pushToTalk && !state.talkHeld) {
      return;
    }
    _stream?.sendAudio(chunk);
  }

  void _sendCommand(HostCommandAction action) {
    if (!state.isLive) return;
    _stream?.send(HostCommandMessage(action));
  }

  void _stopPlayback() {
    _playback.clear();
    _dropAudio = true;
  }

  Future<void> _startCapture() async {
    if (_capturing) return;
    _capturing = true;
    try {
      await _capture.start(_onChunk);
    } catch (_) {
      _capturing = false;
      if (ref.mounted) {
        state = state.copyWith(problem: () => HostProblem.micDenied);
      }
    }
  }

  Future<void> _stopCapture() async {
    if (!_capturing) return;
    _capturing = false;
    await _capture.stop();
  }

  Future<void> _requestWakeLock() async {
    final granted = await _wakeLock.request();
    if (!ref.mounted) return;
    state = state.copyWith(wakeLockDenied: !granted);
  }

  Future<void> _closeStream() async {
    final stream = _stream;
    final subscription = _streamSubscription;
    _stream = null;
    _streamSubscription = null;
    _endTimer?.cancel();
    _endTimer = null;
    _leaving = false;
    _closingUtteranceId = null;
    await subscription?.cancel();
    await stream?.close();
  }

  void _dispose() {
    unawaited(_visibilitySubscription?.cancel());
    unawaited(_closeStream());
    if (_capturing) {
      _capturing = false;
      unawaited(_capture.stop());
    }
    _playback.clear();
    unawaited(_wakeLock.release());
  }

  HostProblem _problemFor(Object error) {
    if (error is ApiException) {
      if (error.statusCode == 422) return HostProblem.invalidPlayerCount;
      if (error.statusCode == 403) return HostProblem.forbidden;
    }
    return HostProblem.unavailable;
  }
}

final hostControllerProvider =
    NotifierProvider.autoDispose<HostController, HostState>(HostController.new);
