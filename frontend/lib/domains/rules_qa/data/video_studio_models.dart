// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'video_studio_models.freezed.dart';
part 'video_studio_models.g.dart';

// ⚠️ 必須和後端 rules_qa 的 schemas 同步
// （規格：openspec/changes/add-rules-video-mobile/specs/rules-video-studio/spec.md）。

/// 影片專案（`GET /api/v1/rules-videos`）。`step`：pages＝還沒有草稿；draft＝有草稿。
@freezed
abstract class VideoProject with _$VideoProject {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoProject({
    required String id,
    required int gameId,
    required String gameName,
    required String shopId,
    required String createdBy,
    required int chapterNumber,
    required String chapterTitle,
    required String step,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _VideoProject;

  factory VideoProject.fromJson(Map<String, dynamic> json) =>
      _$VideoProjectFromJson(json);
}

/// 建立專案。店員的店家用登入身分，不用填。
@freezed
abstract class VideoProjectCreate with _$VideoProjectCreate {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoProjectCreate({
    required int gameId,
    required int chapterNumber,
    required String chapterTitle,
  }) = _VideoProjectCreate;

  factory VideoProjectCreate.fromJson(Map<String, dynamic> json) =>
      _$VideoProjectCreateFromJson(json);
}

/// 建立專案時選的遊戲（`GET /api/v1/games` 的一筆）。
@freezed
abstract class VideoGameOption with _$VideoGameOption {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoGameOption({required int id, required String name}) =
      _VideoGameOption;

  factory VideoGameOption.fromJson(Map<String, dynamic> json) =>
      _$VideoGameOptionFromJson(json);
}

/// 店員刪掉的一段（原文有、編輯後沒有）。
@freezed
abstract class RemovedBlock with _$RemovedBlock {
  const factory RemovedBlock({required List<String> lines}) = _RemovedBlock;

  factory RemovedBlock.fromJson(Map<String, dynamic> json) =>
      _$RemovedBlockFromJson(json);
}

/// 改過的一行（例如修正 OCR 錯字），附原文與編輯後。
@freezed
abstract class ChangedLine with _$ChangedLine {
  const factory ChangedLine({
    required String original,
    required String edited,
    required double similarity,
  }) = _ChangedLine;

  factory ChangedLine.fromJson(Map<String, dynamic> json) =>
      _$ChangedLineFromJson(json);
}

/// 一頁的原文與編輯後的文字。`role`：chapter＝本章頁、reference＝參考頁。
@freezed
abstract class VideoPageText with _$VideoPageText {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoPageText({
    required int page,
    required String role,
    String? original,
    required String text,
    required bool originalChanged,
    required List<RemovedBlock> removed,
    required List<ChangedLine> changed,
  }) = _VideoPageText;

  factory VideoPageText.fromJson(Map<String, dynamic> json) =>
      _$VideoPageTextFromJson(json);
}

/// `GET /api/v1/rules-videos/{id}/pages`。
@freezed
abstract class VideoPages with _$VideoPages {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoPages({
    required List<int> availablePages,
    required List<int> chapterPages,
    required List<int> referencePages,
    required int pagesVersion,
    required List<VideoPageText> pages,
  }) = _VideoPages;

  factory VideoPages.fromJson(Map<String, dynamic> json) =>
      _$VideoPagesFromJson(json);
}

/// `PUT /api/v1/rules-videos/{id}/pages`：沒給文字的頁用原文。
@freezed
abstract class VideoPagesUpdate with _$VideoPagesUpdate {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoPagesUpdate({
    required List<int> chapterPages,
    required List<int> referencePages,
    required Map<String, String> texts,
  }) = _VideoPagesUpdate;

  factory VideoPagesUpdate.fromJson(Map<String, dynamic> json) =>
      _$VideoPagesUpdateFromJson(json);
}

/// 工作的狀態：queued＝等待、running＝處理中、succeeded＝完成、failed＝失敗。
enum VideoJobStatus { queued, running, succeeded, failed }

/// 非同步工作（產生草稿等）。`error` 是給店員看的說明。
@freezed
abstract class VideoJob with _$VideoJob {
  const VideoJob._();

  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoJob({
    required String id,
    required String projectId,
    required String kind,
    required VideoJobStatus status,
    required double progress,
    String? message,
    String? error,
    Map<String, dynamic>? result,
    required DateTime createdAt,
    DateTime? startedAt,
    DateTime? finishedAt,
  }) = _VideoJob;

  factory VideoJob.fromJson(Map<String, dynamic> json) =>
      _$VideoJobFromJson(json);

  /// 還在等待或處理中。
  bool get active =>
      status == VideoJobStatus.queued || status == VideoJobStatus.running;
}

@freezed
abstract class DraftBeat with _$DraftBeat {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftBeat({
    required String beatKey,
    required String narration,
    required String subtitle,
  }) = _DraftBeat;

  factory DraftBeat.fromJson(Map<String, dynamic> json) =>
      _$DraftBeatFromJson(json);
}

@freezed
abstract class DraftSegment with _$DraftSegment {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftSegment({
    required String segmentKey,
    required List<int> sourcePages,
    required List<DraftBeat> beats,
  }) = _DraftSegment;

  factory DraftSegment.fromJson(Map<String, dynamic> json) =>
      _$DraftSegmentFromJson(json);
}

/// 素材清單的一筆。`representative`：泛稱素材，店員可以換成同類的任一張牌。
@freezed
abstract class DraftAsset with _$DraftAsset {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftAsset({
    required String assetKey,
    required String kind,
    required String priority,
    required String reason,
    String? shot,
    required bool representative,
    required List<String> regions,
    required bool hasPhoto,
  }) = _DraftAsset;

  factory DraftAsset.fromJson(Map<String, dynamic> json) =>
      _$DraftAssetFromJson(json);
}

@freezed
abstract class CoverageIssue with _$CoverageIssue {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CoverageIssue({
    required String ruleId,
    required String category,
    required String source,
    required String narrationStatus,
    String? narrationMissing,
    required String subtitleStatus,
    String? subtitleMissing,
    required bool narrationShorter,
  }) = _CoverageIssue;

  factory CoverageIssue.fromJson(Map<String, dynamic> json) =>
      _$CoverageIssueFromJson(json);
}

@freezed
abstract class CoverageProblem with _$CoverageProblem {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CoverageProblem({
    required String beatKey,
    required String track,
    required String kind,
    required String text,
    required String reason,
  }) = _CoverageProblem;

  factory CoverageProblem.fromJson(Map<String, dynamic> json) =>
      _$CoverageProblemFromJson(json);
}

@freezed
abstract class CoverageHint with _$CoverageHint {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CoverageHint({required String ruleId, required String source}) =
      _CoverageHint;

  factory CoverageHint.fromJson(Map<String, dynamic> json) =>
      _$CoverageHintFromJson(json);
}

/// 涵蓋檢查摘要。`status`：done、not_done（附 reason）、stale（旁白或字幕改過）。
@freezed
abstract class DraftCoverage with _$DraftCoverage {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftCoverage({
    required String status,
    String? reason,
    required int totalRules,
    required List<CoverageIssue> issues,
    required List<CoverageProblem> problems,
    required List<CoverageHint> hints,
  }) = _DraftCoverage;

  factory DraftCoverage.fromJson(Map<String, dynamic> json) =>
      _$DraftCoverageFromJson(json);
}

/// 用語對照表狀態：used、empty、missing（從未上傳時附提示）。
@freezed
abstract class DraftTerms with _$DraftTerms {
  const factory DraftTerms({required String status, String? message}) =
      _DraftTerms;

  factory DraftTerms.fromJson(Map<String, dynamic> json) =>
      _$DraftTermsFromJson(json);
}

/// `GET /api/v1/rules-videos/{id}/draft`。
@freezed
abstract class VideoDraft with _$VideoDraft {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoDraft({
    required int videoVersion,
    required List<DraftSegment> segments,
    required List<DraftAsset> assets,
    required DraftCoverage coverage,
    required DraftTerms terms,
    required bool pagesStale,
    String? pagesStaleMessage,
  }) = _VideoDraft;

  factory VideoDraft.fromJson(Map<String, dynamic> json) =>
      _$VideoDraftFromJson(json);
}
