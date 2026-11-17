// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'rules_qa_models.freezed.dart';
part 'rules_qa_models.g.dart';

// ⚠️ 必須和後端 rules_qa 的 schemas 同步
// （規格：openspec/changes/add-rules-qa/specs/rules-qa/spec.md）。

/// `GET /api/v1/rules-lessons` 的一筆：有教材的遊戲。
@freezed
abstract class RulesLessonSummary with _$RulesLessonSummary {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RulesLessonSummary({
    required int gameId,
    required String gameName,
    required bool hasVideo,
    required bool hasRulebook,
  }) = _RulesLessonSummary;

  factory RulesLessonSummary.fromJson(Map<String, dynamic> json) =>
      _$RulesLessonSummaryFromJson(json);
}

/// 影片來源：組內上傳到 YouTube 的影片，或影片生產器產生的 mp4。
enum LessonVideoSource { youtube, file }

/// 教學影片。`source=youtube` 時 [youtubeId] 為 YouTube 影片 ID。
@freezed
abstract class LessonVideo with _$LessonVideo {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory LessonVideo({
    required LessonVideoSource source,
    required String videoUrl,
    String? youtubeId,
    required String title,
  }) = _LessonVideo;

  factory LessonVideo.fromJson(Map<String, dynamic> json) =>
      _$LessonVideoFromJson(json);
}

/// `GET /api/v1/rules-lessons/{game_id}`：某款遊戲的教學內容。
@freezed
abstract class RulesLesson with _$RulesLesson {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RulesLesson({
    required int gameId,
    required String gameName,

    /// 沒有教學影片時為 null。
    required LessonVideo? video,
    required bool hasRulebook,
    required List<String> suggestedQuestions,
  }) = _RulesLesson;

  factory RulesLesson.fromJson(Map<String, dynamic> json) =>
      _$RulesLessonFromJson(json);
}

/// `POST /api/v1/rules-lessons/{game_id}/messages` 的請求。
@freezed
abstract class RulesMessageRequest with _$RulesMessageRequest {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RulesMessageRequest({
    required String content,

    /// 上一則回答的 `response_id`，新對話是 null。後端規定一定要帶這個欄位，null 也要送出。
    @JsonKey(includeIfNull: true) required String? previousResponseId,
  }) = _RulesMessageRequest;

  factory RulesMessageRequest.fromJson(Map<String, dynamic> json) =>
      _$RulesMessageRequestFromJson(json);
}

/// 回答引用的出處：規則書第幾頁。
@freezed
abstract class Citation with _$Citation {
  const factory Citation({required int page}) = _Citation;

  factory Citation.fromJson(Map<String, dynamic> json) =>
      _$CitationFromJson(json);
}

/// 規則問答的回答。教材中找不到時 `answerable=false`、沒有出處。
@freezed
abstract class RulesAnswer with _$RulesAnswer {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RulesAnswer({
    required String responseId,
    required String answer,
    required bool answerable,
    required List<Citation> citations,
  }) = _RulesAnswer;

  factory RulesAnswer.fromJson(Map<String, dynamic> json) =>
      _$RulesAnswerFromJson(json);
}
