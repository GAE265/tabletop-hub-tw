// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'game_option.freezed.dart';
part 'game_option.g.dart';

@freezed
abstract class GameOption with _$GameOption {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GameOption({
    required int id,
    required String name,
    required String englishName,
  }) = _GameOption;

  factory GameOption.fromJson(Map<String, dynamic> json) =>
      _$GameOptionFromJson(json);
}

@freezed
abstract class GameSearchResult with _$GameSearchResult {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory GameSearchResult({
    required List<GameOption> items,
    required int total,
  }) = _GameSearchResult;

  factory GameSearchResult.fromJson(Map<String, dynamic> json) =>
      _$GameSearchResultFromJson(json);
}
