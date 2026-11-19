// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'group_notification.freezed.dart';
part 'group_notification.g.dart';

/// 揪團通知（`GET /api/v1/group-notifications` 的一筆）。時間為 UTC。
///
/// `type`：group_confirmed（成團）／group_cancelled（解散）／waitlist_promoted（候補正取）。
/// `readAt` 為 null 代表未讀。
@freezed
abstract class GroupNotification with _$GroupNotification {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GroupNotification({
    required String id,
    required String type,
    required NotificationGroupRef group,
    DateTime? readAt,
    required DateTime createdAt,
  }) = _GroupNotification;

  factory GroupNotification.fromJson(Map<String, dynamic> json) =>
      _$GroupNotificationFromJson(json);
}

/// 通知所屬的揪團：目前的名稱與開始時間。
@freezed
abstract class NotificationGroupRef with _$NotificationGroupRef {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory NotificationGroupRef({
    required String id,
    required String title,
    required DateTime startAt,
  }) = _NotificationGroupRef;

  factory NotificationGroupRef.fromJson(Map<String, dynamic> json) =>
      _$NotificationGroupRefFromJson(json);
}

/// 通知的分頁回應；`unreadCount` 是全部未讀的數量，不受分頁影響。
@freezed
abstract class GroupNotificationPage with _$GroupNotificationPage {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GroupNotificationPage({
    required List<GroupNotification> items,
    required int total,
    required int unreadCount,
  }) = _GroupNotificationPage;

  factory GroupNotificationPage.fromJson(Map<String, dynamic> json) =>
      _$GroupNotificationPageFromJson(json);
}
