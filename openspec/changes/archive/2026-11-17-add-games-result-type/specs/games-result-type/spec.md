# Spec Delta

## Purpose

記錄每款桌遊的結果該怎麼記（陣營勝負、個人分數、合作過關），讓戰績功能能依遊戲選擇對應的紀錄方式。這是遊戲本身的屬性，存在共用表 `games`。

## ADDED Requirements

### Requirement: games 有結果類型欄位
共用表 `games` SHALL 有文字欄位 `result_type`，值只能是 `faction`（陣營勝負）、`score`（個人分數）、`cooperative`（合作）。限制 MUST 由資料庫 CHECK 執行，欄位型別 MUST 是文字，不使用 PostgreSQL 原生 enum。

#### Scenario: 寫入 faction
- **WHEN** 寫入或更新一款桌遊，`result_type` 為 `faction`
- **THEN** 寫入成功，讀回的值為 `faction`

#### Scenario: 寫入 score
- **WHEN** 寫入或更新一款桌遊，`result_type` 為 `score`
- **THEN** 寫入成功，讀回的值為 `score`

#### Scenario: 寫入 cooperative
- **WHEN** 寫入或更新一款桌遊，`result_type` 為 `cooperative`
- **THEN** 寫入成功，讀回的值為 `cooperative`

#### Scenario: 不合法的值
- **WHEN** 寫入 `result_type` 為 `ranking`、空字串或大小寫不同的 `Faction`
- **THEN** 資料庫拒絕該筆寫入，該款桌遊維持原狀

### Requirement: 結果類型可以為空
`result_type` SHALL 允許為空，空值代表「這款遊戲還沒設定結果類型」。既有桌遊在升級後 MUST 保持原有資料不變，`result_type` 為空。

#### Scenario: 不給 result_type 寫入
- **WHEN** 寫入一款桌遊，不提供 `result_type`
- **THEN** 寫入成功，讀回 `result_type` 為空

#### Scenario: 升級既有資料庫
- **WHEN** 對已有桌遊資料的資料庫執行 `alembic upgrade head`
- **THEN** 升級成功，既有桌遊的其他欄位不變、`result_type` 皆為空

#### Scenario: 降版
- **WHEN** 執行 `alembic downgrade -1` 退回此 migration 之前
- **THEN** `result_type` 欄位與其 CHECK 被移除，其他欄位與資料不變

### Requirement: 結果類型有中文說明
`result_type` 欄位 MUST 有中文 comment，說明記錄什麼與空值代表什麼；Python 端的 `ResultType` Enum 每個值 MUST 有中文註解，說明代表什麼並舉遊戲為例。

#### Scenario: 資料庫裡看得到說明
- **WHEN** 查詢 `games.result_type` 的欄位 comment
- **THEN** 取得非空的中文說明，且提到空值的意義

### Requirement: 匯入、匯出、同步桌遊資料帶有結果類型
`games.json`、匯出檔與同步 MUST 處理 `result_type`：檔案裡的該欄位可以省略或為 null（視為空），有值時 MUST 是三個合法值之一；其他值 MUST 被驗證擋下，且資料庫沒有任何變動。匯出檔 MUST 包含每款桌遊目前的 `result_type`。

#### Scenario: 匯出含 result_type
- **WHEN** 資料庫裡有 `result_type` 為 `score` 與為空的兩款桌遊，執行匯出桌遊
- **THEN** 匯出成功，兩款分別帶 `score` 與 null

#### Scenario: 匯入有值
- **WHEN** `games.json` 某款桌遊的 `result_type` 為 `cooperative`，執行匯入桌遊
- **THEN** 該款寫入時 `result_type` 為 `cooperative`

#### Scenario: 舊格式的檔案
- **WHEN** 匯入或同步沒有 `result_type` 欄位的舊格式檔案
- **THEN** 驗證通過，`result_type` 視為空

#### Scenario: 檔案裡的值不合法
- **WHEN** 匯入或同步的檔案中某款桌遊 `result_type` 為 `ranking`
- **THEN** 驗證失敗並指出是哪一款，資料庫沒有任何變動

#### Scenario: 同步會蓋掉資料庫裡的值
- **WHEN** 資料庫某款 `result_type` 為 `score`，匯出檔裡同一款為空，執行同步
- **THEN** 同步後該款 `result_type` 為空（同步的結果和匯出檔完全一樣）

### Requirement: 既有推薦 API 的回應格式不變
推薦對話 API 回傳的桌遊卡片 MUST NOT 因為新增 `result_type` 而多出欄位。

#### Scenario: 推薦卡片欄位
- **WHEN** 資料庫的桌遊有 `result_type` 值，呼叫推薦對話 API 取得推薦卡片
- **THEN** `game` 物件的欄位與新增 `result_type` 前相同，不含 `result_type`
