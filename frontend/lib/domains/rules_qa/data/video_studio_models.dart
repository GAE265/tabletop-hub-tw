// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'video_studio_models.freezed.dart';
part 'video_studio_models.g.dart';

// ⚠️ 必須和後端 rules_qa 的 schemas 同步
// （規格：openspec/changes/add-rules-video-mobile/specs/rules-video-studio/spec.md）。

/// 影片專案（`GET /api/v1/rules-videos`）。整個遊戲一支影片（D17）時章節是 null。
/// `step`：draft＝產生草稿中或有草稿、還沒拍照；assets＝素材還沒齊；render＝齊了、還沒有成品；
/// done＝有成品；pages＝舊的單章專案還沒有草稿。
@freezed
abstract class VideoProject with _$VideoProject {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoProject({
    required String id,
    required int gameId,
    required String gameName,
    required String shopId,
    required String createdBy,
    int? chapterNumber,
    String? chapterTitle,
    // 影片標題：整個遊戲是「〈遊戲〉 規則教學」
    required String title,
    required String step,
    // 規則書來源：imported＝管理員匯入的；photos＝店員拍規則書（2026-11-22 永傑決定）
    @Default('imported') String rulebook,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _VideoProject;

  factory VideoProject.fromJson(Map<String, dynamic> json) =>
      _$VideoProjectFromJson(json);
}

/// 建立專案：只選遊戲（整個遊戲一支影片，建立後後端自動產生草稿）。店員的店家用登入身分。
@freezed
abstract class VideoProjectCreate with _$VideoProjectCreate {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory VideoProjectCreate({
    required int gameId,
    // 'photos'＝拍規則書；null＝用已匯入的規則書（不送這個欄位）
    String? rulebook,
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

/// 放牌的格子裡的一張牌；沒有牌背時 `backAssetKey` 是 null。
@freezed
abstract class DraftItem with _$DraftItem {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftItem({
    required String itemKey,
    required String assetKey,
    String? backAssetKey,
  }) = _DraftItem;

  factory DraftItem.fromJson(Map<String, dynamic> json) =>
      _$DraftItemFromJson(json);
}

/// 一段裡放素材的格子（換素材，2026-11-25）。`kind`：asset＝單一素材、items＝放好幾張牌。
@freezed
abstract class DraftSlot with _$DraftSlot {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftSlot({
    // 格子名稱：main（主畫面）、sidebar（側欄）
    required String slot,
    required String kind,
    // 這一格用到的素材（依出現順序、不重複；牌的正面與牌背都算）
    required List<String> assetKeys,
    // 可以換素材（完整版：單一素材的格子、放牌的格子都可以）
    required bool swappable,
    // 放牌的格子的每一張牌；單一素材的格子是空的
    @Default([]) List<DraftItem> items,
  }) = _DraftSlot;

  factory DraftSlot.fromJson(Map<String, dynamic> json) =>
      _$DraftSlotFromJson(json);
}

@freezed
abstract class DraftSegment with _$DraftSegment {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DraftSegment({
    required String segmentKey,
    // 屬於哪一格：setup＝開局、round＝走完一輪、win＝獲勝方式
    @Default('') String chapter,
    required List<int> sourcePages,
    required List<DraftBeat> beats,
    // 放素材的格子（換素材，2026-11-25）
    @Default([]) List<DraftSlot> slots,
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
    // 給店員看的中文名稱；舊的草稿沒有
    String? label,
    required String kind,
    required String priority,
    required String reason,
    String? shot,
    required bool representative,
    required List<String> regions,
    // 已經標好座標的區域（重新產生草稿前提示要重標）
    @Default([]) List<String> markedRegions,
    required bool hasPhoto,
    // 店員略過的素材（MR 9）
    @Default(false) bool skipped,
    // 可以略過：略過後每一段仍有主要內容（後端程式判斷，不看 priority）
    @Default(false) bool skippable,
    // 用到這個素材的段號；[] 代表沒有段在用、不用拍；null 代表舊的回應沒有這個資訊
    List<int>? usedInSegments,
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

/// 一格（開局、走完一輪、獲勝方式）的涵蓋檢查。`status`：done、not_done（附 reason）。
@freezed
abstract class CoverageSlot with _$CoverageSlot {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CoverageSlot({
    required String slot,
    required String title,
    required String status,
    String? reason,
    required int totalRules,
    required List<CoverageIssue> issues,
    required List<CoverageProblem> problems,
    required List<CoverageHint> hints,
  }) = _CoverageSlot;

  factory CoverageSlot.fromJson(Map<String, dynamic> json) =>
      _$CoverageSlotFromJson(json);
}

/// 涵蓋檢查摘要。`status`：done、not_done（附 reason）、stale（旁白或字幕改過）。
/// `slots`：依格的摘要（整個遊戲一支影片）；合計是三格加起來。
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
    @Default([]) List<CoverageSlot> slots,
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

/// 一個素材的明細（`GET /api/v1/rules-videos/{id}/assets/{asset_key}`，MR 7）。
/// `orientation`：照片需要順時針轉幾度才會擺正。`regions`：名稱 → [x, y, w, h]（0–1 的比例，
/// 以套用方向之後的圖為準）；null＝待量測。
@freezed
abstract class VideoAsset with _$VideoAsset {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoAsset({
    required String assetKey,
    // 給店員看的中文名稱；舊的草稿沒有
    String? label,
    required String kind,
    required String priority,
    required String reason,
    String? shot,
    required bool hasPhoto,
    required int orientation,
    required Map<String, List<double>?> regions,
    // 區域名稱 → 給店員的白話說明（只在標區域畫面顯示）；舊的草稿沒有
    @Default({}) Map<String, String> regionHints,
    // 區域名稱 → 用到它的段（段號從 1 開始）
    @Default({}) Map<String, List<int>> regionSegments,
    // 照片拍不到、店員略過的區域
    @Default([]) List<String> skippedRegions,
    required int videoVersion,
    // 略過（MR 9）：可不可以略過由後端程式判斷（skippable，不看 priority）；
    // 略過後會少一張圖的段、只靠它而不能略過的段（段號從 1 開始）
    @Default(false) bool skipped,
    @Default(false) bool skippable,
    @Default([]) List<int> skipAffectedSegments,
    @Default([]) List<int> skipBlockedSegments,
  }) = _VideoAsset;

  factory VideoAsset.fromJson(Map<String, dynamic> json) =>
      _$VideoAssetFromJson(json);
}

/// 換某一段某一格的素材（2026-11-25；完整版）。放牌的格子另給 `itemKey` 與 `face`
/// （front 正面／back 牌背）。`videoVersion` 是店員看到的草稿版本，不同時後端回 409。
@freezed
abstract class SegmentSwapInput with _$SegmentSwapInput {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory SegmentSwapInput({
    required String slot,
    required String assetKey,
    String? itemKey,
    @Default('front') String face,
    required int videoVersion,
  }) = _SegmentSwapInput;

  factory SegmentSwapInput.fromJson(Map<String, dynamic> json) =>
      _$SegmentSwapInputFromJson(json);
}

/// 換素材的結果。框線、標籤、動作都保留；`regionsToMark` 是新素材上要重標的區域。
@freezed
abstract class SegmentSwapResult with _$SegmentSwapResult {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SegmentSwapResult({
    required String segmentKey,
    required String slot,
    String? itemKey,
    @Default('front') String face,
    required String oldAssetKey,
    required String newAssetKey,
    required List<String> regionsToMark,
    // 換完之後沒有段在用的素材：不用再拍
    required List<String> unusedAssets,
    required int videoVersion,
  }) = _SegmentSwapResult;

  factory SegmentSwapResult.fromJson(Map<String, dynamic> json) =>
      _$SegmentSwapResultFromJson(json);
}

/// 新增一個照片素材（換素材時，正確的素材不在清單裡）；`shot` 是拍攝說明（選填）。
@freezed
abstract class VideoAssetCreate with _$VideoAssetCreate {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory VideoAssetCreate({
    required String label,
    String? shot,
    required int videoVersion,
  }) = _VideoAssetCreate;

  factory VideoAssetCreate.fromJson(Map<String, dynamic> json) =>
      _$VideoAssetCreateFromJson(json);
}

/// 改方向或區域；沒給的欄位不送。只改方向時，後端把區域改回待量測。
@freezed
abstract class VideoAssetUpdate with _$VideoAssetUpdate {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory VideoAssetUpdate({
    int? orientation,
    Map<String, List<double>?>? regions,
    // true 略過、false 取消略過
    bool? skipped,
    // 照片拍不到的區域（整份取代；[] 取消全部）
    List<String>? skippedRegions,
  }) = _VideoAssetUpdate;

  factory VideoAssetUpdate.fromJson(Map<String, dynamic> json) =>
      _$VideoAssetUpdateFromJson(json);
}

/// 還沒有照片的素材（都會擋住產生影片）。`skippable`：可以略過（後端程式判斷）；
/// `priority` 是 AI 標的必拍／選拍，畫面不再使用。
@freezed
abstract class MissingPhoto with _$MissingPhoto {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MissingPhoto({
    required String assetKey,
    // 給店員看的名稱（中文名稱；舊的草稿是 reason）
    @Default('') String label,
    required String priority,
    @Default(false) bool skippable,
    required String reason,
    String? shot,
    @Default([]) List<int> skipAffectedSegments,
    @Default([]) List<int> skipBlockedSegments,
  }) = _MissingPhoto;

  factory MissingPhoto.fromJson(Map<String, dynamic> json) =>
      _$MissingPhotoFromJson(json);
}

@freezed
abstract class MissingRegion with _$MissingRegion {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MissingRegion({
    required String assetKey,
    required String region,
  }) = _MissingRegion;

  factory MissingRegion.fromJson(Map<String, dynamic> json) =>
      _$MissingRegionFromJson(json);
}

/// 本版不支援的素材（繪製素材）。
@freezed
abstract class UnsupportedAsset with _$UnsupportedAsset {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory UnsupportedAsset({
    required String assetKey,
    required String kind,
    required String message,
  }) = _UnsupportedAsset;

  factory UnsupportedAsset.fromJson(Map<String, dynamic> json) =>
      _$UnsupportedAssetFromJson(json);
}

/// 產生影片前還缺什麼（`GET /api/v1/rules-videos/{id}/readiness`）。
@freezed
abstract class VideoReadiness with _$VideoReadiness {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoReadiness({
    required bool ready,
    required List<MissingPhoto> missingPhotos,
    required List<MissingRegion> missingRegions,
    required List<UnsupportedAsset> unsupported,
  }) = _VideoReadiness;

  factory VideoReadiness.fromJson(Map<String, dynamic> json) =>
      _$VideoReadinessFromJson(json);
}

/// 最近一次成功產生的影片（`GET /api/v1/rules-videos/{id}/render`，MR 9）。
/// `estimated`：沒有設定文字轉語音，旁白靜音、時間為估計值。
@freezed
abstract class VideoRender with _$VideoRender {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoRender({
    required String jobId,
    required String videoPath,
    required double totalSeconds,
    required List<String> reencoded,
    required List<String> reused,
    required List<String> skippedAssets,
    required bool estimated,
    required List<String> warnings,
    // 段清單（看影片頁點一段跳到那個時間點）
    @Default([]) List<RenderSegment> segments,
    DateTime? finishedAt,
  }) = _VideoRender;

  factory VideoRender.fromJson(Map<String, dynamic> json) =>
      _$VideoRenderFromJson(json);
}

/// 成品的一段：第一句開始的秒數與字幕。
@freezed
abstract class RenderSegment with _$RenderSegment {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RenderSegment({
    required String segmentKey,
    required double startSeconds,
    required String title,
  }) = _RenderSegment;

  factory RenderSegment.fromJson(Map<String, dynamic> json) =>
      _$RenderSegmentFromJson(json);
}

/// 一張規則書照片（店員拍規則書）。`quality`：ok｜warn（可能讀錯，建議重拍）｜bad（太模糊，請重拍）。
@freezed
abstract class RulebookPhoto with _$RulebookPhoto {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RulebookPhoto({
    // 不隨刪除改變的代號（縮圖快取用）
    required String id,
    // 第幾張（從 1 開始），就是頁的順序
    required int index,
    required int width,
    required int height,
    required String quality,
    String? qualityMessage,
  }) = _RulebookPhoto;

  factory RulebookPhoto.fromJson(Map<String, dynamic> json) =>
      _$RulebookPhotoFromJson(json);
}

/// 照片模式專案的規則書照片；`read`＝這些照片都讀過了（重新產生草稿不會再讀）。
@freezed
abstract class Rulebook with _$Rulebook {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory Rulebook({
    required List<RulebookPhoto> photos,
    required bool read,
  }) = _Rulebook;

  factory Rulebook.fromJson(Map<String, dynamic> json) =>
      _$RulebookFromJson(json);
}

// --------------------------------------------------------------------------- 用一句話修改（MR 11、12）

/// 送出修改要求（`POST /rules-videos/{id}/revisions`）；`segmentKey` 指定只改哪一段（選填）。
@freezed
abstract class VideoRevisionCreate with _$VideoRevisionCreate {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory VideoRevisionCreate({
    required String request,
    String? segmentKey,
    required int videoVersion,
  }) = _VideoRevisionCreate;

  factory VideoRevisionCreate.fromJson(Map<String, dynamic> json) =>
      _$VideoRevisionCreateFromJson(json);
}

/// 套用提案或選的替代做法（`PATCH /rules-videos/{id}/revisions/{revision_id}`）。
@freezed
abstract class VideoRevisionApply with _$VideoRevisionApply {
  @JsonSerializable(fieldRename: FieldRename.snake, includeIfNull: false)
  const factory VideoRevisionApply({
    @Default('applied') String status,
    // 版型做不到時選的替代做法（從 1 開始）
    int? alternative,
    required int videoVersion,
  }) = _VideoRevisionApply;

  factory VideoRevisionApply.fromJson(Map<String, dynamic> json) =>
      _$VideoRevisionApplyFromJson(json);
}

@freezed
abstract class RevisionText with _$RevisionText {
  const factory RevisionText({
    required String narration,
    required String subtitle,
  }) = _RevisionText;

  factory RevisionText.fromJson(Map<String, dynamic> json) =>
      _$RevisionTextFromJson(json);
}

/// 旁白或字幕有變的一句；新增的句子 `before` 是 null，刪除的句子 `after` 是 null。
@freezed
abstract class RevisionBeat with _$RevisionBeat {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RevisionBeat({
    required String beatKey,
    RevisionText? before,
    RevisionText? after,
  }) = _RevisionBeat;

  factory RevisionBeat.fromJson(Map<String, dynamic> json) =>
      _$RevisionBeatFromJson(json);
}

/// 提案裡的一段：AI 的說明、改了哪些欄位分類、改了但沒被要求的分類、旁白字幕的前後對照。
@freezed
abstract class RevisionSegment with _$RevisionSegment {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RevisionSegment({
    required String segmentKey,
    required int segmentNumber,
    required String summary,
    required List<String> changed,
    required List<String> unrequested,
    @Default([]) List<RevisionBeat> beats,
  }) = _RevisionSegment;

  factory RevisionSegment.fromJson(Map<String, dynamic> json) =>
      _$RevisionSegmentFromJson(json);
}

/// 版型做不到時的替代做法；套用時帶 `number`。
@freezed
abstract class RevisionAlternative with _$RevisionAlternative {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RevisionAlternative({
    required int number,
    required String title,
    required String description,
    @Default([]) List<RevisionSegment> segments,
  }) = _RevisionAlternative;

  factory RevisionAlternative.fromJson(Map<String, dynamic> json) =>
      _$RevisionAlternativeFromJson(json);
}

/// 不確定改哪一段時的候選段。
@freezed
abstract class RevisionCandidate with _$RevisionCandidate {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RevisionCandidate({
    required String segmentKey,
    required int segmentNumber,
    required String reason,
  }) = _RevisionCandidate;

  factory RevisionCandidate.fromJson(Map<String, dynamic> json) =>
      _$RevisionCandidateFromJson(json);
}

/// 一次修改的進度與結果；`id` 是修改的工作編號。
/// `outcome`：proposal＝可以做、unsupported＝版型做不到（看替代做法）、
/// ambiguous＝不確定改哪一段（選一段後重新送出）；還沒算完或失敗時是 null。
@freezed
abstract class VideoRevision with _$VideoRevision {
  const VideoRevision._();

  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory VideoRevision({
    required String id,
    required String projectId,
    required VideoJobStatus status,
    required double progress,
    String? message,
    String? error,
    required String request,
    String? segmentKey,
    String? outcome,
    String? reason,
    @Default([]) List<RevisionSegment> segments,
    @Default([]) List<RevisionAlternative> alternatives,
    @Default([]) List<RevisionCandidate> candidates,
    @Default(false) bool manySegments,
    @Default(false) bool applied,
    int? appliedAlternative,
    // 套用後的段資料版本
    int? videoVersion,
    @Default(false) bool coverageChecked,
    String? coverageMessage,
  }) = _VideoRevision;

  factory VideoRevision.fromJson(Map<String, dynamic> json) =>
      _$VideoRevisionFromJson(json);

  /// AI 還在算。
  bool get active =>
      status == VideoJobStatus.queued || status == VideoJobStatus.running;
}
