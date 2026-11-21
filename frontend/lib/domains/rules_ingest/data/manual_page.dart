// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'manual_page.freezed.dart';
part 'manual_page.g.dart';

@freezed
abstract class ManualPage with _$ManualPage {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory ManualPage({
    required int page,
    required String content,
    @Default(0) int chunkCount,
  }) = _ManualPage;

  factory ManualPage.fromJson(Map<String, dynamic> json) =>
      _$ManualPageFromJson(json);
}

@freezed
abstract class ManualPageList with _$ManualPageList {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory ManualPageList({
    required List<ManualPage> items,
    required int total,
    required String ocrProvider,
  }) = _ManualPageList;

  factory ManualPageList.fromJson(Map<String, dynamic> json) =>
      _$ManualPageListFromJson(json);
}
