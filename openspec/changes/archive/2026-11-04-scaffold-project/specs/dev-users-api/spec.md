# Spec Delta

## Purpose

讓前端身分切換器從後端取得測試帳號清單，使測試帳號的 UUID 只在後端定義一處，且僅存在於開發模式。

## ADDED Requirements

### Requirement: 列出測試帳號
`AUTH_MODE=dev` 時，`GET /api/v1/dev/users` SHALL 回傳 200 與 `{"items": [...], "total": n}`，每筆含 `id`（UUID）、`display_name`、`role`、`shop_id`（可為 null）；內容 MUST 為 seed 所建立的 player、shop_staff、admin 三個帳號。

#### Scenario: seed 之後查詢
- **WHEN** 已執行 seed 後呼叫 `GET /api/v1/dev/users`
- **THEN** 回 200，`total` 為 3，`items` 的角色各為 `player`、`shop_staff`、`admin` 一個，shop_staff 的 `shop_id` 不為 null

#### Scenario: 與資料庫一致
- **WHEN** 比對回應的 `id` 與 `auth_users` 中對應的列
- **THEN** UUID、`display_name`、`role`、`shop_id` 完全相同

#### Scenario: 尚未 seed
- **WHEN** 資料庫沒有任何測試帳號時呼叫該端點
- **THEN** 回 200，`items` 為空陣列、`total` 為 0

#### Scenario: 不需身分
- **WHEN** 不帶 `X-Dev-User` 呼叫該端點
- **THEN** 回 200，不回 401

#### Scenario: 只列測試帳號
- **WHEN** `auth_users` 中另有非 seed 的使用者
- **THEN** 回應 MUST NOT 包含這些使用者

### Requirement: 非 dev 模式不存在此端點
`AUTH_MODE` 不是 `dev` 時，系統 MUST NOT 掛載 `/api/v1/dev/...` 任何路由。

#### Scenario: jwt 模式
- **WHEN** `AUTH_MODE=jwt` 時呼叫 `GET /api/v1/dev/users`
- **THEN** 回 404，body 為統一錯誤格式

#### Scenario: 不出現在 OpenAPI
- **WHEN** `AUTH_MODE=jwt` 時檢視 `/openapi.json`
- **THEN** 不含 `/api/v1/dev/users`

### Requirement: 測試帳號 UUID 單一來源
測試帳號與測試店家的 UUID SHALL 只定義在後端 `app/dev/`（預設玩家的 UUID 例外，見 design.md D7）；前端 MUST NOT 內嵌任何測試帳號 UUID。

#### Scenario: 前端無寫死 UUID
- **WHEN** 在 `frontend/` 原始碼搜尋 seed 使用的三組 UUID
- **THEN** 沒有任何符合

#### Scenario: seed 與端點同源
- **WHEN** 修改 `app/dev/` 內某帳號的 UUID 後重新 seed
- **THEN** `GET /api/v1/dev/users` 回傳新值，其他程式碼無需修改

### Requirement: app/dev 不被其他程式碼依賴
`app/dev/` MAY 使用任何 domain 的程式，但其他任何程式碼（含測試）MUST NOT import `app/dev/`。

#### Scenario: 靜態檢查
- **WHEN** 搜尋 `backend/` 中對 `app.dev` 的 import（`app/dev/` 自身除外）
- **THEN** 沒有任何符合

#### Scenario: 無 dev 路由時應用仍可啟動
- **WHEN** `AUTH_MODE=jwt` 啟動應用
- **THEN** 啟動成功，且過程中未載入 `app/dev/` 模組
