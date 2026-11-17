## ADDED Requirements

### Requirement: 規則書頁面資料表
系統 SHALL 有資料表 `games_manual`，每一列是某款桌遊的某一頁規則書文字：`games_id`（bigint，參照 `games.id`）、`page`（integer，從 1 開始）、`content`（text，Markdown，可為空字串）。主鍵 MUST 是 `(games_id, page)`，同一款桌遊的同一頁只會有一列。

#### Scenario: 寫入一頁
- **WHEN** 對存在的桌遊寫入 `page = 9`、`content` 為一段 Markdown
- **THEN** 寫入成功，資料表有一列 `(games_id, 9, content)`

#### Scenario: 同一頁不可重複
- **WHEN** 以 INSERT 對同一個 `(games_id, page)` 寫入第二列
- **THEN** 資料庫拒絕該筆寫入（違反主鍵）

#### Scenario: 缺號的頁碼
- **WHEN** 同一款桌遊只寫入第 1、3 頁
- **THEN** 兩列都存在，第 2 頁沒有列，資料庫不要求頁碼連續

#### Scenario: 整頁沒文字
- **WHEN** 寫入 `content` 為空字串 `""`
- **THEN** 寫入成功，該列存在且 `content` 為空字串

### Requirement: 頁碼從 1 開始
`page` MUST 大於或等於 1，由資料庫的檢查約束保證。

#### Scenario: 頁碼為 0
- **WHEN** 寫入 `page = 0`
- **THEN** 資料庫拒絕該筆寫入

#### Scenario: 頁碼為負數
- **WHEN** 寫入 `page = -1`
- **THEN** 資料庫拒絕該筆寫入

### Requirement: 桌遊必須存在，且不隨桌遊刪除
`games_manual.games_id` MUST 是指向 `games.id` 的外鍵，且 MUST NOT 設定 `ON DELETE CASCADE`（ADR 0003）。

#### Scenario: 桌遊不存在
- **WHEN** 寫入的 `games_id` 在 `games` 中找不到
- **THEN** 資料庫拒絕該筆寫入（違反外鍵）

#### Scenario: 刪除還有規則書的桌遊
- **WHEN** 嘗試刪除一款在 `games_manual` 還有資料的桌遊
- **THEN** 資料庫拒絕刪除，規則書各頁仍在

#### Scenario: 刪除沒有規則書的桌遊
- **WHEN** 刪除一款在 `games_manual` 沒有資料的桌遊
- **THEN** 刪除成功

### Requirement: 以 repository 覆蓋寫入單頁
`rules_ingest` 的 repository SHALL 提供依 `(games_id, page)` 覆蓋寫入的操作：該頁不存在就新增，已存在就以新的 `content` 取代，不報錯、不產生第二列。

#### Scenario: 新增
- **WHEN** 對沒有資料的 `(1, 9)` 執行覆蓋寫入
- **THEN** 新增一列，內容為傳入的 `content`

#### Scenario: 覆蓋
- **WHEN** `(1, 9)` 已有內容，再以不同的 `content` 執行覆蓋寫入
- **THEN** 該列的 `content` 變成新的內容，`(1, 9)` 仍只有一列

#### Scenario: 覆蓋成空字串
- **WHEN** `(1, 9)` 已有內容，以 `""` 執行覆蓋寫入
- **THEN** 該列的 `content` 變成空字串，不會被當成沒有資料而略過

#### Scenario: 不影響其他頁
- **WHEN** 覆蓋寫入 `(1, 9)`
- **THEN** `(1, 8)` 與 `(2, 9)` 的內容不變

#### Scenario: 桌遊不存在
- **WHEN** 對不存在的 `games_id` 執行覆蓋寫入
- **THEN** 拋出錯誤，不寫入任何資料（由 service 之後轉成 404）

### Requirement: migration 可往返
migration `0003` MUST 能升級與降級；降級只移除 `games_manual`，不動 `games` 等其他表。

#### Scenario: 升級
- **WHEN** 在已升級到 `0002` 的資料庫執行 `alembic upgrade head`
- **THEN** `games_manual` 存在，具備上述主鍵、外鍵與頁碼約束

#### Scenario: 降級
- **WHEN** 執行 `alembic downgrade 0002`
- **THEN** `games_manual` 不存在，`games`、`genres`、`game_genres` 仍在
