## ADDED Requirements

### Requirement: 查詢桌子狀態
系統 SHALL 提供 `GET /api/v1/shops/{shop_id}/tables/status` 端點，回傳指定樓層所有啟用中桌子的座標與該時段的佔用狀態。查詢參數 MAY 包含 `from`、`to`（ISO 8601 UTC）與 `floor`；未帶 `from`/`to` 時 SHALL 查詢當天 00:00 至 23:59:59（Asia/Taipei）；未帶 `floor` 時 SHALL 回傳所有樓層的桌子。玩家、店家人員、管理員皆可呼叫。

#### Scenario: 查詢指定時段有桌位被佔用
- **WHEN** 店家人員查詢 `GET /api/v1/shops/{shop_id}/tables/status?from=2026-11-17T06:00:00Z&to=2026-11-17T10:00:00Z&floor=1`，且該時段內 A 桌有已確認訂位
- **THEN** 回傳 200，A 桌 `status` 為 `unavailable`，`booking` 包含該訂位的摘要資訊（`id`、`reservation_code`、`user_id`、`start_at`、`end_at`、`party_size`、`status`）

#### Scenario: 查詢時段無任何訂位
- **WHEN** 店家人員查詢 1F，且該時段無任何有效訂位
- **THEN** 所有桌子 `status` 為 `available`，`booking` 為 `null`

#### Scenario: 未帶時間參數查整天
- **WHEN** 請求不帶 `from` 與 `to` 參數
- **THEN** 系統以當天 Asia/Taipei 的 00:00 至 23:59:59 為查詢範圍

#### Scenario: 未帶樓層參數回傳所有樓層
- **WHEN** 請求不帶 `floor` 參數
- **THEN** 回傳所有樓層（1F 與 B1）的桌子

#### Scenario: 僅已確認與已入座訂位視為佔用
- **WHEN** A 桌有 `pending` 或 `cancelled` 或 `no_show` 或 `completed` 的訂位
- **THEN** A 桌 `status` 為 `available`

#### Scenario: 玩家只能看到自己訂位的 booking 資訊
- **WHEN** 玩家查詢，且 A 桌被其他玩家的訂位佔用
- **THEN** A 桌 `status` 為 `unavailable`，但 `booking` 為 `null`

#### Scenario: 玩家可以看到自己訂位的 booking 資訊
- **WHEN** 玩家查詢，且 A 桌被該玩家自己的訂位佔用
- **THEN** A 桌 `status` 為 `unavailable`，且 `booking` 包含該訂位摘要

#### Scenario: 店家不存在
- **WHEN** 查詢不存在的 `shop_id`
- **THEN** 回傳 404，`BOOKING_SHOP_NOT_FOUND`

#### Scenario: 未登入
- **WHEN** 不帶認證資訊查詢
- **THEN** 回傳 401
