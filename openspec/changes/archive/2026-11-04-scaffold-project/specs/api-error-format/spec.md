# Spec Delta

## Purpose

讓所有 domain 的錯誤回應格式一致，前端只需寫一套錯誤處理。

## ADDED Requirements

### Requirement: 錯誤回應統一格式
所有 4xx／5xx 回應 SHALL 為 `{"error": {"code": str, "message": str, "details": object}}`，`code` 為大寫 `SNAKE_CASE`。

#### Scenario: 找不到路徑
- **WHEN** 呼叫不存在的路徑
- **THEN** 回 404，body 為 `{"error": {"code": "NOT_FOUND", ...}}`

#### Scenario: 欄位驗證失敗
- **WHEN** 請求欄位不符 schema
- **THEN** 回 422，`error.code` 為 `VALIDATION_ERROR`，`details` 列出出錯欄位

#### Scenario: 未預期例外
- **WHEN** 處理請求時拋出未處理例外
- **THEN** 回 500，`error.code` 為 `INTERNAL_ERROR`，`message` MUST NOT 洩漏堆疊或內部細節

### Requirement: 權限不足轉為 403
當程式拋出 `PermissionDenied`，系統 SHALL 回 403 與統一錯誤格式，`error.code` 為 `PERMISSION_DENIED`。

#### Scenario: 角色不符
- **WHEN** 端點內呼叫角色檢查且使用者角色不在允許清單
- **THEN** 回 403，`error.code` 為 `PERMISSION_DENIED`

### Requirement: 領域錯誤可帶自訂代碼
系統 SHALL 提供可由各 domain 拋出的應用程式例外，攜帶 HTTP 狀態碼、`code`、`message`、`details`，並由同一處理器轉成統一格式。

#### Scenario: 狀態衝突
- **WHEN** 某端點拋出 409 且 code 為 `BOOKING_TABLE_TAKEN` 的應用程式例外
- **THEN** 回 409，body 的 `error.code` 為 `BOOKING_TABLE_TAKEN`
