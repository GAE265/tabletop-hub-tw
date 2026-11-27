// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

import 'game_match.dart';

part 'match_notification.freezed.dart';
part 'match_notification.g.dart';

/// 戰績通知（`GET /api/v1/match-notifications` 的一筆）。時間為 UTC。
///
/// `type`：match_result_recorded（這一局的結果被記錄或覆蓋，請確認）。
/// `readAt` 為 null 代表未讀。
@freezed
abstract class MatchNotification with _$MatchNotification {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MatchNotification({
    required String id,
    required String type,
    required NotificationMatchRef match,

    /// 記錄（或覆蓋）結果、觸發這則通知的人。
    required MatchUserRef recordedBy,
    DateTime? readAt,
    required DateTime createdAt,
  }) = _MatchNotification;

  factory MatchNotification.fromJson(Map<String, dynamic> json) =>
      _$MatchNotificationFromJson(json);
}

/// 通知的那一局：遊戲名稱與進行的日期。
@freezed
abstract class NotificationMatchRef with _$NotificationMatchRef {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory NotificationMatchRef({
    required String id,
    required String gameName,
    required DateTime playedOn,
  }) = _NotificationMatchRef;

  factory NotificationMatchRef.fromJson(Map<String, dynamic> json) =>
      _$NotificationMatchRefFromJson(json);
}

/// 通知的分頁回應；`unreadCount` 是全部未讀的數量，不受分頁影響。
@freezed
abstract class MatchNotificationPage with _$MatchNotificationPage {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MatchNotificationPage({
    required List<MatchNotification> items,
    required int total,
    required int unreadCount,
  }) = _MatchNotificationPage;

  factory MatchNotificationPage.fromJson(Map<String, dynamic> json) =>
      _$MatchNotificationPageFromJson(json);
}
