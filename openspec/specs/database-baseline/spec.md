# database-baseline Specification

## Purpose

建立資料庫起點：向量擴充，以及 `auth_users` 與 `booking_shops` 兩張共用資料表（皆列於 AGENTS.md 第 3 節「共用資料表」），讓各 domain 之後的 migration 有穩定的外鍵目標。

## Requirements

### Requirement: 第一個 migration 建立基底
第一個 Alembic migration SHALL 啟用 pgvector 擴充，並建立 `auth_users`（`id`、`display_name`、`role`、`shop_id` 可為空、`created_at`）與 `booking_shops`（`id`、`name`）。

#### Scenario: 從空資料庫升級
- **WHEN** 對空的 PostgreSQL 16 + pgvector 執行 `alembic upgrade head`
- **THEN** `vector` 擴充已啟用，且兩張表存在並含上述欄位

#### Scenario: 角色限制
- **WHEN** 嘗試寫入 `auth_users.role` 為 `organizer`
- **THEN** 資料庫拒絕該筆寫入（角色僅限 `player`、`shop_staff`、`admin`）

#### Scenario: 店家關聯
- **WHEN** `auth_users.shop_id` 指向不存在的 `booking_shops.id`
- **THEN** 資料庫拒絕該筆寫入

### Requirement: 主鍵一律為 UUID
所有資料表的主鍵 `id` SHALL 為 UUID 型別，資料庫端 MUST 有預設值，使不指定 `id` 的寫入也能成功；參照欄位（如 `shop_id`）同為 UUID。

#### Scenario: 欄位型別
- **WHEN** 檢視 `auth_users.id`、`booking_shops.id`、`auth_users.shop_id` 的型別
- **THEN** 皆為 UUID

#### Scenario: 未指定 id 的寫入
- **WHEN** 寫入 `booking_shops` 時不提供 `id`
- **THEN** 寫入成功，且 `id` 為自動產生的 UUID

#### Scenario: 呼叫端自行指定 id
- **WHEN** 寫入時提供事先產生的 UUID 作為 `id`
- **THEN** 以該值儲存，不被覆蓋

### Requirement: migration 不含帳號與種子資料
migration MUST NOT 寫入任何測試帳號或示範資料；這類資料只能由開發用 seed 指令建立。

#### Scenario: 升級後資料表為空
- **WHEN** 只執行 `alembic upgrade head`
- **THEN** `auth_users` 與 `booking_shops` 筆數為 0

### Requirement: migration 可回退
第一個 migration SHALL 提供 downgrade，使 `alembic downgrade base` 後上述資料表被移除。

#### Scenario: 升級後降級
- **WHEN** 依序執行 `upgrade head` 與 `downgrade base`
- **THEN** `auth_users` 與 `booking_shops` 不存在，且命令成功結束

### Requirement: 資料庫存取為同步
後端 SHALL 以同步 session 存取資料庫，不使用 async。

#### Scenario: health 使用同步連線
- **WHEN** 檢視 health 的資料庫檢查與 session 依賴
- **THEN** 皆為同步呼叫

### Requirement: 向量維度由設定提供
骨架 MUST NOT 在程式碼中寫死向量維度；維度 SHALL 為設定項，供之後含向量欄位的 migration 使用。

#### Scenario: 設定存在
- **WHEN** 檢視設定與 `.env.example`
- **THEN** 有向量維度欄位及說明
