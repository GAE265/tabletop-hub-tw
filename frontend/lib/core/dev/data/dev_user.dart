// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'dev_user.freezed.dart';
part 'dev_user.g.dart';

/// 後端 `GET /api/v1/dev/users` 回傳的測試帳號。UUID 只存在後端，這裡不寫死。
@freezed
abstract class DevUser with _$DevUser {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DevUser({
    required String id,
    required String displayName,
    required String role,
    String? shopId,
  }) = _DevUser;

  factory DevUser.fromJson(Map<String, dynamic> json) =>
      _$DevUserFromJson(json);
}
