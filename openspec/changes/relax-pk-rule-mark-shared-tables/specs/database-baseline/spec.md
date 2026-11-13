# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: 主鍵一律為 UUID`
- TO: `### Requirement: 主鍵預設為 UUID`

## MODIFIED Requirements

### Requirement: 主鍵預設為 UUID
資料表的主鍵 `id` 預設 SHALL 為 UUID 型別，資料庫端 MUST 有預設值，使不指定 `id` 的寫入也能成功；參照 UUID 主鍵的欄位（如 `shop_id`）同為 UUID。固定的小型分類表（如 `game_types`）MAY 使用 `bigint` identity 作為主鍵。

#### Scenario: 欄位型別
- **WHEN** 檢視 `auth_users.id`、`booking_shops.id`、`auth_users.shop_id` 的型別
- **THEN** 皆為 UUID

#### Scenario: 未指定 id 的寫入
- **WHEN** 寫入 `booking_shops` 時不提供 `id`
- **THEN** 寫入成功，且 `id` 為自動產生的 UUID

#### Scenario: 呼叫端自行指定 id
- **WHEN** 寫入時提供事先產生的 UUID 作為 `id`
- **THEN** 以該值儲存，不被覆蓋

#### Scenario: 固定小型分類表使用流水號
- **WHEN** 固定的小型分類表（如 `game_types`）以 `bigint` identity 作為主鍵
- **THEN** 不違反本需求，其餘資料表的主鍵仍預設為 UUID
