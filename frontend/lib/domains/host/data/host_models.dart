// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'host_models.freezed.dart';
part 'host_models.g.dart';

// ⚠️ 必須和後端 host 的 schemas 同步（規格：.scratch/host/spec.md §11、§12）。

/// 一場主持的狀態。主持暫停不是狀態，是進行中的一個標記。
@JsonEnum(valueField: 'wire')
enum HostStatus {
  active('active'),
  ended('ended');

  const HostStatus(this.wire);
  final String wire;
}

/// 接話方式。
@JsonEnum(valueField: 'wire')
enum TurnTakingMode {
  /// 自動接話（預設）。
  auto('auto'),

  /// 按住說話。
  pushToTalk('push_to_talk');

  const TurnTakingMode(this.wire);
  final String wire;
}

/// 主持人的聲線。開始後這場主持不能換。
@JsonEnum(valueField: 'wire')
enum HostVoice {
  male('male'),
  female('female');

  const HostVoice(this.wire);
  final String wire;
}

/// 流程走到哪個節點（spec §3.1）。
@JsonEnum(valueField: 'wire')
enum HostStep {
  opening('opening'),
  setup('setup'),
  night1('night_1'),
  night2('night_2'),
  turn('turn'),
  ended('ended');

  const HostStep(this.wire);
  final String wire;
}

/// 贏的一方。
@JsonEnum(valueField: 'wire')
enum HostWinner {
  whiteRose('white_rose'),
  bloodBlade('blood_blade');

  const HostWinner(this.wire);
  final String wire;
}

/// 主持暫停的原因。
@JsonEnum(valueField: 'wire')
enum HostPauseReason {
  /// 說「等一下」「暫停」或按暫停鍵。
  command('command'),

  /// 頁面被切走或鎖屏。
  pageHidden('page_hidden'),

  /// 同一段被閒聊切斷太多次。
  chatter('chatter');

  const HostPauseReason(this.wire);
  final String wire;
}

/// 一場主持（三個一般請求都用同一個格式，spec §11.2）。
@freezed
abstract class HostingSession with _$HostingSession {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory HostingSession({
    required String id,
    required HostStatus status,
    required int playerCount,
    required TurnTakingMode turnTakingMode,
    required HostVoice voice,
    required HostStep step,

    /// 開場到夜晚是 null。
    int? turnNumber,

    /// 開場到夜晚是 null。
    int? phaseNumber,
    required bool paused,

    /// 還沒分出勝負，或結束時不分陣營，是 null。
    HostWinner? winner,
    required DateTime createdAt,
  }) = _HostingSession;

  factory HostingSession.fromJson(Map<String, dynamic> json) =>
      _$HostingSessionFromJson(json);
}

/// 連 WebSocket 用的一次性通行碼，60 秒內有效。
@freezed
abstract class HostConnectionTicket with _$HostConnectionTicket {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory HostConnectionTicket({
    required String ticket,
    required DateTime expiresAt,
  }) = _HostConnectionTicket;

  factory HostConnectionTicket.fromJson(Map<String, dynamic> json) =>
      _$HostConnectionTicketFromJson(json);
}

/// 開主持與拿通行碼的回應：這場主持加上通行碼。
@freezed
abstract class HostingSessionAccess with _$HostingSessionAccess {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory HostingSessionAccess({
    required HostingSession session,
    required HostConnectionTicket connection,
  }) = _HostingSessionAccess;

  factory HostingSessionAccess.fromJson(Map<String, dynamic> json) =>
      _$HostingSessionAccessFromJson(json);
}

/// `POST /api/v1/hosting-sessions` 的請求。
@freezed
abstract class CreateHostingSessionRequest with _$CreateHostingSessionRequest {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CreateHostingSessionRequest({
    required int playerCount,
    required TurnTakingMode turnTakingMode,
    required HostVoice voice,
  }) = _CreateHostingSessionRequest;

  factory CreateHostingSessionRequest.fromJson(Map<String, dynamic> json) =>
      _$CreateHostingSessionRequestFromJson(json);
}

/// WebSocket `state` 訊息：現況。連上時送一次，之後有變就送整份（spec §12.4）。
@freezed
abstract class HostLiveState with _$HostLiveState {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory HostLiveState({
    required HostStatus status,
    required HostStep step,
    int? turnNumber,
    int? phaseNumber,
    required bool paused,

    /// 不在暫停中是 null。
    HostPauseReason? pauseReason,

    /// 查規則或等思考模型時是 true，頁面顯示「正在查規則」。
    required bool lookingUp,
    required TurnTakingMode turnTakingMode,
    required HostVoice voice,
    HostWinner? winner,
  }) = _HostLiveState;

  factory HostLiveState.fromJson(Map<String, dynamic> json) =>
      _$HostLiveStateFromJson(json);
}
