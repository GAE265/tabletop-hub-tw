// freezed 的 @JsonSerializable 寫在 factory 上，分析器會誤報 invalid_annotation_target。
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'health_status.freezed.dart';
part 'health_status.g.dart';

/// `GET /api/v1/health` 的回應。`status` 為 ok／degraded，`database` 為 up／down。
@freezed
abstract class HealthStatus with _$HealthStatus {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory HealthStatus({
    required String status,
    required String database,
  }) = _HealthStatus;

  factory HealthStatus.fromJson(Map<String, dynamic> json) =>
      _$HealthStatusFromJson(json);
}
