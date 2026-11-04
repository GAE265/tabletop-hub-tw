# health-check Specification

## Purpose

提供單一端點讓前端、CI 與部署平台確認後端服務與資料庫是否可用。

## Requirements

### Requirement: 健康檢查回報服務與資料庫狀態
`GET /api/v1/health` SHALL 回傳 200 與 JSON，含 `status`（`ok` 或 `degraded`）與 `database`（`up` 或 `down`）；該端點 MUST NOT 需要登入。

#### Scenario: 資料庫正常
- **WHEN** 資料庫可連線時呼叫 `GET /api/v1/health`
- **THEN** 回 200，`{"status": "ok", "database": "up"}`

#### Scenario: 資料庫中斷
- **WHEN** 資料庫無法連線時呼叫 `GET /api/v1/health`
- **THEN** 回 200，`{"status": "degraded", "database": "down"}`，服務本身不崩潰

#### Scenario: 不需身分
- **WHEN** 不帶 `X-Dev-User` 標頭呼叫該端點
- **THEN** 回 200，不回 401

#### Scenario: 不支援的方法
- **WHEN** 以 `POST` 呼叫 `/api/v1/health`
- **THEN** 回 405，body 為統一錯誤格式
