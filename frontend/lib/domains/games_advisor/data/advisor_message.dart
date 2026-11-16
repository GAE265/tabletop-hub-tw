// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'advisor_message.freezed.dart';
part 'advisor_message.g.dart';

// ⚠️ 必須和後端 backend/app/domains/games_advisor/schemas.py 的
// MessageRequest、MessageResponse 同步（spec §13.1）。

/// `POST /api/v1/advisor/messages` 的請求。
@freezed
abstract class AdvisorMessageRequest with _$AdvisorMessageRequest {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory AdvisorMessageRequest({
    required String content,

    /// 上一則回應的 `response_id`，新對話是 null。
    /// 後端規定這個欄位一定要帶，漏了會回 422，所以 null 也要送出。
    @JsonKey(includeIfNull: true) required String? previousResponseId,
  }) = _AdvisorMessageRequest;

  factory AdvisorMessageRequest.fromJson(Map<String, dynamic> json) =>
      _$AdvisorMessageRequestFromJson(json);
}

/// 推薦時放寬了哪個條件；整則訊息一個值。
enum RelaxedConstraint { playtime, age }

/// `POST /api/v1/advisor/messages` 的回應。
@freezed
abstract class AdvisorMessageResponse with _$AdvisorMessageResponse {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory AdvisorMessageResponse({
    /// 下一則訊息要帶回去的 id。固定文字時是請求帶來的舊 id；
    /// 第一則訊息就是固定文字時是 null。
    required String? responseId,
    required String reply,
    required RelaxedConstraint? relaxedConstraint,

    /// 最多 3 張卡片；追問、離題、查無結果、固定文字時是空的。
    required List<AdvisorRecommendation> recommendations,
  }) = _AdvisorMessageResponse;

  factory AdvisorMessageResponse.fromJson(Map<String, dynamic> json) =>
      _$AdvisorMessageResponseFromJson(json);
}

/// 一張推薦卡片：桌遊、推薦理由、被引用的心得片段。
@freezed
abstract class AdvisorRecommendation with _$AdvisorRecommendation {
  const factory AdvisorRecommendation({
    required AdvisorGame game,
    required String reason,
    required List<AdvisorExcerpt> excerpts,
  }) = _AdvisorRecommendation;

  factory AdvisorRecommendation.fromJson(Map<String, dynamic> json) =>
      _$AdvisorRecommendationFromJson(json);
}

/// 卡片上的桌遊基本資料。`weight` 是 1–5 的難度原值，畫面再四捨五入。
@freezed
abstract class AdvisorGame with _$AdvisorGame {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory AdvisorGame({
    required int id,
    required String name,
    required int minPlayers,
    required int maxPlayers,
    required int minPlaytime,
    required int maxPlaytime,
    required int minAge,
    required double weight,
  }) = _AdvisorGame;

  factory AdvisorGame.fromJson(Map<String, dynamic> json) =>
      _$AdvisorGameFromJson(json);
}

/// 心得片段原文。`language` 是 `zh-TW` 或 `en`；不含來源。
@freezed
abstract class AdvisorExcerpt with _$AdvisorExcerpt {
  const factory AdvisorExcerpt({
    required String id,
    required String text,
    required String language,
  }) = _AdvisorExcerpt;

  factory AdvisorExcerpt.fromJson(Map<String, dynamic> json) =>
      _$AdvisorExcerptFromJson(json);
}
