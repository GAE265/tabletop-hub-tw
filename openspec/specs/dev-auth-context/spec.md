# dev-auth-context Specification

## Purpose

在 JWT 登入完成前，讓所有 domain 能取得「目前使用者」並寫授權邏輯與測試；`auth` 完成後只替換取得方式，不影響 domain。

## Requirements

### Requirement: dev 模式由標頭決定使用者
當 `AUTH_MODE=dev`，系統 SHALL 從請求標頭 `X-Dev-User`（格式 `<user_uuid>:<role>[:<shop_uuid>]`）取得目前使用者，不查詢任何資料表；`role` 為 `shop_staff` 時 `shop_uuid` 必填，其他角色 MUST NOT 帶；未帶標頭時 MUST 使用預設測試玩家；預設玩家的 UUID 由設定提供，且與 seed 的 player 帳號相同。

#### Scenario: 玩家帶有效標頭
- **WHEN** 請求帶 `X-Dev-User: <某 UUID>:player`
- **THEN** 目前使用者 id 為該 UUID、角色為 `player`、`shop_id` 為空

#### Scenario: shop_staff 帶店家
- **WHEN** 請求帶 `X-Dev-User: <使用者 UUID>:shop_staff:<店家 UUID>`
- **THEN** 目前使用者角色為 `shop_staff`，`shop_id` 為該店家 UUID

#### Scenario: shop_staff 缺店家
- **WHEN** 請求帶 `X-Dev-User: <UUID>:shop_staff`（或第三段為空）
- **THEN** 回 400，`error.code` 為 `INVALID_DEV_USER`

#### Scenario: player 多帶店家
- **WHEN** 請求帶 `X-Dev-User: <UUID>:player:<店家 UUID>`
- **THEN** 回 400，`error.code` 為 `INVALID_DEV_USER`

#### Scenario: admin 多帶店家
- **WHEN** 請求帶 `X-Dev-User: <UUID>:admin:<店家 UUID>`
- **THEN** 回 400，`error.code` 為 `INVALID_DEV_USER`

#### Scenario: 店家不是合法 UUID
- **WHEN** 請求帶 `X-Dev-User: <UUID>:shop_staff:not-a-uuid`
- **THEN** 回 400，`error.code` 為 `INVALID_DEV_USER`

#### Scenario: 未帶標頭
- **WHEN** 請求不帶 `X-Dev-User`
- **THEN** 目前使用者為預設測試玩家，角色為 `player`

#### Scenario: 標頭格式錯誤
- **WHEN** `X-Dev-User` 的使用者不是合法 UUID（例如 `7:player`）、角色不是 `player`／`shop_staff`／`admin`，或段數不是 2～3 段
- **THEN** 回 400，統一錯誤格式

### Requirement: 目前使用者不查詢資料表
`CurrentUser` MUST 只從請求帶來的資訊（開發標頭，之後是 JWT）建立；取得目前使用者的過程 MUST NOT 查詢任何資料表。

#### Scenario: 資料庫不可用時仍可取得身分
- **WHEN** 資料庫無法連線時，以有效的 `X-Dev-User` 呼叫只需要身分的端點
- **THEN** 端點仍可取得目前使用者，不因資料庫而失敗

### Requirement: 非 dev 模式不接受開發標頭
當 `AUTH_MODE` 不是 `dev`，系統 MUST 忽略 `X-Dev-User`；骨架階段 `jwt` 模式 SHALL 對需要身分的端點回 401。

#### Scenario: jwt 模式帶開發標頭
- **WHEN** `AUTH_MODE=jwt` 且請求帶有效格式的 `X-Dev-User` 呼叫需要身分的端點
- **THEN** 回 401，統一錯誤格式

### Requirement: 角色檢查
`require_role(user, *roles)` SHALL 在使用者角色不在 `roles` 時拋出 `PermissionDenied`，否則不做任何事。

#### Scenario: 角色符合
- **WHEN** 角色為 `player` 且允許 `player`、`admin`
- **THEN** 檢查通過

#### Scenario: 角色不符
- **WHEN** 角色為 `player` 且只允許 `shop_staff`、`admin`
- **THEN** 拋出 `PermissionDenied`

### Requirement: 開發用測試帳號由 seed 建立
系統 SHALL 在 `app/dev/` 提供開發用 seed 指令，建立固定 UUID 的 player、shop_staff、admin 各一個帳號（shop_staff 隸屬一間固定 UUID 的測試店家）；該指令 MUST 可重複執行而不產生重複資料，且 MUST NOT 內含於 migration。

#### Scenario: 首次執行
- **WHEN** 在已升級的空資料庫執行 seed 指令
- **THEN** `auth_users` 出現三筆固定 UUID 的帳號，shop_staff 的 `shop_id` 指向測試店家

#### Scenario: 重複執行
- **WHEN** 連續執行 seed 指令兩次
- **THEN** 資料筆數與第一次相同，指令成功結束

#### Scenario: jwt 模式拒絕執行
- **WHEN** `AUTH_MODE=jwt` 時執行 seed 指令
- **THEN** 指令以非零狀態結束並說明原因，資料庫未被寫入

#### Scenario: 預設玩家與 seed 一致
- **WHEN** seed 之後以 dev 模式、不帶標頭呼叫需要身分的端點
- **THEN** 目前使用者的 id 等於 seed 建立的 player 帳號 id

#### Scenario: migration 不含帳號
- **WHEN** 對空資料庫只執行 `alembic upgrade head`
- **THEN** `auth_users` 與 `booking_shops` 為空

### Requirement: 測試身分 fixture
測試環境 SHALL 提供 `as_player`、`as_shop_staff`、`as_admin` 三個 fixture，以依賴覆寫切換目前使用者，且不經過登入流程、不依賴 seed。

#### Scenario: 切換為店家人員
- **WHEN** 測試使用 `as_shop_staff`
- **THEN** 該測試中取得的目前使用者角色為 `shop_staff` 且帶有 `shop_id`

#### Scenario: 切換為管理員
- **WHEN** 測試使用 `as_admin`
- **THEN** 該測試中取得的目前使用者角色為 `admin`
