# frontend-shell Specification

## Purpose

提供 Flutter Web 前端的共用外殼與 health 範例，示範 AGENTS.md 第 5 節的分層與參考畫面／正式頁面分工。

## Requirements

### Requirement: API 位址由編譯參數注入
前端 SHALL 從 `--dart-define=API_BASE_URL=...` 取得後端位址；程式碼 MUST NOT 內嵌任何秘密。

#### Scenario: 有指定位址
- **WHEN** 以 `API_BASE_URL=http://localhost:8000` 執行
- **THEN** API 請求發往該位址

#### Scenario: 未指定位址
- **WHEN** 未提供 `API_BASE_URL`
- **THEN** 使用文件載明的本機預設值

### Requirement: RWD 斷點集中定義
系統 SHALL 在 `core/layout/` 定義斷點：寬度 < 600 為手機、< 1024 為平板、其餘為桌機；各頁面 MUST NOT 自訂斷點。

#### Scenario: 邊界值
- **WHEN** 寬度為 599、600、1023、1024
- **THEN** 分別判定為手機、平板、平板、桌機

### Requirement: 參考畫面路由由旗標控制
`/proto/...` 路由 SHALL 只在 `--dart-define=SHOW_PROTOTYPES=true` 時註冊。

#### Scenario: 旗標開啟
- **WHEN** `SHOW_PROTOTYPES=true` 並前往 `/proto/health`
- **THEN** 顯示 health 參考畫面

#### Scenario: 旗標關閉
- **WHEN** 未設定 `SHOW_PROTOTYPES` 並前往 `/proto/health`
- **THEN** 顯示找不到頁面，不顯示參考畫面

### Requirement: 開發環境自動帶身分標頭
在開發環境，API client SHALL 對每個請求帶 `X-Dev-User: <user_uuid>:<role>[:<shop_uuid>]`（`shop_staff` 帶其 `shop_id`，其他角色不帶）；身分預設為 player。正式環境 MUST NOT 帶該標頭。

#### Scenario: 預設身分
- **WHEN** 開發環境啟動後未切換身分即發出請求
- **THEN** 標頭為 `GET /api/v1/dev/users` 回傳的 player 帳號 id 加 `:player`（不帶店家）

#### Scenario: 切換為店家人員
- **WHEN** 開發者在切換器選擇 shop_staff 帳號
- **THEN** 之後的請求標頭為該帳號的 id 加 `:shop_staff:` 加其 `shop_id`

#### Scenario: 帳號清單載入前
- **WHEN** 帳號清單尚未載入或載入失敗時發出請求
- **THEN** 請求不帶 `X-Dev-User`（由後端使用預設玩家），應用不崩潰

#### Scenario: 正式環境
- **WHEN** 以正式環境設定建置
- **THEN** 請求不含 `X-Dev-User`

### Requirement: 開發身分切換器
前端 SHALL 在 `core/dev/` 提供身分切換器，由 `GET /api/v1/dev/users` 取得測試帳號清單供開發者選擇，無需手動輸入 UUID；切換器 MUST 只在開發環境出現，且前端 MUST NOT 內嵌任何測試帳號 UUID。

#### Scenario: 切換身分
- **WHEN** 開發者在切換器選擇清單中的 admin 帳號
- **THEN** 之後的請求標頭為該帳號的 id 加 `:admin`

#### Scenario: 清單載入失敗
- **WHEN** `GET /api/v1/dev/users` 回 404 或網路失敗
- **THEN** 切換器顯示錯誤與重試，不崩潰

#### Scenario: 清單為空
- **WHEN** 回應 `items` 為空（尚未 seed）
- **THEN** 切換器顯示「尚無測試帳號，請先執行 seed」類提示

#### Scenario: 正式環境隱藏
- **WHEN** 以正式環境設定建置
- **THEN** 畫面上沒有切換器，且不會呼叫 `/api/v1/dev/users`

### Requirement: health 範例示範分層
health domain SHALL 以 `data/`（呼叫 API）、`state/`（Riverpod provider）、`prototypes/health/`（預設元件）與 `pages/`（套主題）示範；`pages/` 與 `prototypes/` MUST 共用同一個 `state/`，且不直接呼叫 API。

#### Scenario: 載入成功
- **WHEN** 後端回報 `ok`
- **THEN** 參考畫面與正式頁面皆顯示服務正常

#### Scenario: 載入中與錯誤
- **WHEN** 請求進行中，或後端無法連線
- **THEN** 兩種畫面分別顯示載入中與錯誤訊息（含重試）

### Requirement: 顏色字級間距只出現在主題
顏色、字級、間距 SHALL 只定義於 `app/theme/`，`pages/` 不得寫死數值。

#### Scenario: 正式頁面取用主題
- **WHEN** 檢視 health 正式頁面
- **THEN** 樣式來自主題，而非頁面內的字面數值
