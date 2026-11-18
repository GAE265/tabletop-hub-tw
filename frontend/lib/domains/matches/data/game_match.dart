// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'game_match.freezed.dart';
part 'game_match.g.dart';

/// 一局遊戲的回應（`GET /api/v1/matches/{id}` 等）。
///
/// 類別叫 [GameMatch]，因為 `Match` 是 Dart 內建的正規表示式類別。
/// `status`：in_progress（進行中）／finished（已結束）；`locationType`：shop（桌遊店）／home（自家）。
/// `isValid` 由後端計算：已記錄結果，且有帳號的參加者都已確認。
@freezed
abstract class GameMatch with _$GameMatch {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GameMatch({
    required String id,
    required MatchGameRef game,
    required DateTime playedOn,
    required String locationType,
    MatchShopRef? shop,
    String? groupId,
    required MatchUserRef createdBy,
    required String status,
    Map<String, dynamic>? result,
    String? progress,
    required List<MatchParticipant> participants,
    required List<MatchTurn> turns,
    required int participantCount,
    required int accountCount,
    required int confirmedCount,
    required bool isValid,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _GameMatch;

  factory GameMatch.fromJson(Map<String, dynamic> json) =>
      _$GameMatchFromJson(json);
}

@freezed
abstract class MatchGameRef with _$MatchGameRef {
  const factory MatchGameRef({required int id, required String name}) =
      _MatchGameRef;

  factory MatchGameRef.fromJson(Map<String, dynamic> json) =>
      _$MatchGameRefFromJson(json);
}

@freezed
abstract class MatchShopRef with _$MatchShopRef {
  const factory MatchShopRef({required String id, required String name}) =
      _MatchShopRef;

  factory MatchShopRef.fromJson(Map<String, dynamic> json) =>
      _$MatchShopRefFromJson(json);
}

@freezed
abstract class MatchUserRef with _$MatchUserRef {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MatchUserRef({
    required String id,
    required String displayName,
  }) = _MatchUserRef;

  factory MatchUserRef.fromJson(Map<String, dynamic> json) =>
      _$MatchUserRefFromJson(json);
}

/// 參加者。`userId` 為空代表沒有帳號（只有名字）；`isWinner`、`score`、`placement`
/// 為空代表尚未記錄或不適用（不是 false、不是 0）。
@freezed
abstract class MatchParticipant with _$MatchParticipant {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MatchParticipant({
    required String id,
    required int seatNumber,
    String? userId,
    required String displayName,
    String? faction,
    int? score,
    int? placement,
    bool? isWinner,
    required bool isConfirmed,
  }) = _MatchParticipant;

  factory MatchParticipant.fromJson(Map<String, dynamic> json) =>
      _$MatchParticipantFromJson(json);
}

/// 一個回合的紀錄。[gameData] 的格式依遊戲而定（白薔薇見 `WhiteRoseTurnData`）。
@freezed
abstract class MatchTurn with _$MatchTurn {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory MatchTurn({
    required String id,
    required int turnNumber,
    required int seatNumber,
    required Map<String, dynamic> gameData,
    required String recordedBy,
    required DateTime updatedAt,
  }) = _MatchTurn;

  factory MatchTurn.fromJson(Map<String, dynamic> json) =>
      _$MatchTurnFromJson(json);
}

/// `GET /api/v1/matches` 的分頁回應。
class MatchPage {
  const MatchPage({required this.items, required this.total});

  factory MatchPage.fromJson(Map<String, dynamic> json) => MatchPage(
    items: [
      for (final item in json['items'] as List<dynamic>)
        GameMatch.fromJson(item as Map<String, dynamic>),
    ],
    total: json['total'] as int,
  );

  final List<GameMatch> items;
  final int total;
}
