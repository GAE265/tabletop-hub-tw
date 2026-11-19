// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'group.freezed.dart';
part 'group.g.dart';

/// 揪團的回應（`GET /api/v1/groups/{id}` 等）。時間為 UTC。
///
/// `status`：open／cancelled／ended；`myStatus`：member／waitlisted／null（未報名）。
@freezed
abstract class Group with _$Group {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory Group({
    required String id,
    required String title,
    String? description,
    required DateTime startAt,
    required DateTime endAt,
    required int capacity,
    int? fee,
    required String status,
    required ShopRef shop,
    required UserRef organizer,

    /// 要玩的遊戲，依開團主選擇的順序；沒有遊戲時是空陣列。
    @Default(<GameRef>[]) List<GameRef> games,
    required int memberCount,
    required int waitlistCount,
    required int remainingSlots,
    String? myStatus,

    /// 開團主確定成團的時間；null 代表還沒確定成團。
    DateTime? confirmedAt,
    required DateTime createdAt,
  }) = _Group;

  factory Group.fromJson(Map<String, dynamic> json) => _$GroupFromJson(json);
}

@freezed
abstract class ShopRef with _$ShopRef {
  const factory ShopRef({required String id, required String name}) = _ShopRef;

  factory ShopRef.fromJson(Map<String, dynamic> json) =>
      _$ShopRefFromJson(json);
}

@freezed
abstract class UserRef with _$UserRef {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory UserRef({required String id, required String displayName}) =
      _UserRef;

  factory UserRef.fromJson(Map<String, dynamic> json) =>
      _$UserRefFromJson(json);
}

@freezed
abstract class GameRef with _$GameRef {
  const factory GameRef({required int id, required String name}) = _GameRef;

  factory GameRef.fromJson(Map<String, dynamic> json) =>
      _$GameRefFromJson(json);
}

/// `GET /api/v1/groups` 的分頁回應。
@freezed
abstract class GroupPage with _$GroupPage {
  const factory GroupPage({required List<Group> items, required int total}) =
      _GroupPage;

  factory GroupPage.fromJson(Map<String, dynamic> json) =>
      _$GroupPageFromJson(json);
}

/// `POST /api/v1/groups/{id}/members` 的回應。額滿時 status=waitlisted 並附候補順位。
@freezed
abstract class JoinResult with _$JoinResult {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory JoinResult({
    required String userId,
    required String status,
    int? waitlistPosition,
  }) = _JoinResult;

  factory JoinResult.fromJson(Map<String, dynamic> json) =>
      _$JoinResultFromJson(json);
}

/// `GET /api/v1/groups/{id}/members` 的一筆：先列成員，再列候補。
@freezed
abstract class GroupMember with _$GroupMember {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GroupMember({
    required String userId,
    required String displayName,
    required String status,
    int? waitlistPosition,
    required DateTime joinedAt,
  }) = _GroupMember;

  factory GroupMember.fromJson(Map<String, dynamic> json) =>
      _$GroupMemberFromJson(json);
}
