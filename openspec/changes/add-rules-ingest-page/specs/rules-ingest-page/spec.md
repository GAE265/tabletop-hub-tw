# Spec Delta

## Purpose

規則書匯入的正式頁面 `/rules-ingest`：管理員選桌遊與圖片，逐頁匯入並讀回已入庫的頁面。

## ADDED Requirements

### Requirement: 只有管理員可以使用
`/rules-ingest` SHALL 只對管理員顯示匯入功能。玩家與店家人員開啟時，顯示「只有管理員可以匯入規則書」，MUST NOT 載入遊戲清單或呼叫匯入 API。

#### Scenario: 管理員
- **WHEN** 管理員開啟 `/rules-ingest`
- **THEN** 顯示匯入頁面並載入遊戲清單

#### Scenario: 其他人
- **WHEN** 玩家或店家人員開啟 `/rules-ingest`
- **THEN** 顯示「只有管理員可以匯入規則書」，不載入遊戲清單

### Requirement: 匯入規則書圖片
頁面 SHALL 使用 `rules_ingest` 的 `state/`（`manualImportProvider`、`manualPagesProvider`），不直接呼叫 API：
- 桌遊欄位可輸入過濾並從下拉選取；起始頁碼預設 1，小於 1 時顯示「起始頁碼必須大於或等於 1」。
- 「選擇 JPEG／PNG 圖片」後列出每張圖片的縮圖、檔名與「→ 匯入為第 N 頁」，可拖曳調整順序、按「移除」刪除。
- 「匯入」只有在選了桌遊、起始頁碼有效、有圖片時才可按；匯入中顯示進度「匯入中：N／M」，每一頁顯示「第 N 頁：檔名」與「成功」或錯誤訊息；單頁失敗不中止後續頁面；完成後自動讀回。
- 匯入或選圖進行中，所有欄位與按鈕停用。

#### Scenario: 缺少欄位
- **WHEN** 還沒選桌遊或沒有圖片
- **THEN** 「匯入」停用

#### Scenario: 起始頁碼錯誤
- **WHEN** 起始頁碼輸入 0
- **THEN** 顯示「起始頁碼必須大於或等於 1」，「匯入」停用

#### Scenario: 選圖片
- **WHEN** 選了 a.png、b.png，起始頁碼 3
- **THEN** 依檔名列出兩張，分別標示「→ 匯入為第 3 頁」「→ 匯入為第 4 頁」

#### Scenario: 移除圖片
- **WHEN** 按第一張的「移除」
- **THEN** 只剩 b.png，標示「→ 匯入為第 3 頁」

#### Scenario: 匯入成功
- **WHEN** 選桌遊、選圖片後按「匯入」
- **THEN** 每一頁顯示「成功」，並自動讀回已入庫頁面

#### Scenario: 單頁失敗
- **WHEN** 第 2 頁回 503
- **THEN** 第 2 頁顯示錯誤訊息，其他頁照常匯入並顯示「成功」

### Requirement: 讀回已入庫頁面
「讀回已入庫頁面」SHALL 在選了桌遊時可按，讀回後顯示 OCR 實作提示（`fake`：「OCR：fake（內容不是真實辨識結果）」；`cloud`：「OCR：cloud」與「使用雲端 OCR 匯入會產生費用」），並逐頁列出頁碼與內容；空字串顯示「（整頁沒文字）」，沒有頁面時顯示「這款桌遊還沒有規則書頁面」。還沒讀回時顯示「請先讀回，確認目前 OCR 實作；cloud 匯入會產生費用」。

#### Scenario: fake
- **WHEN** 讀回空列表，OCR 是 fake
- **THEN** 顯示「這款桌遊還沒有規則書頁面」與 fake 提示

#### Scenario: cloud
- **WHEN** 匯入後自動讀回，OCR 是 cloud
- **THEN** 顯示「OCR：cloud」與「使用雲端 OCR 匯入會產生費用」

#### Scenario: 整頁沒文字
- **WHEN** 某頁內容是空字串
- **THEN** 顯示「（整頁沒文字）」

### Requirement: 版面
手機（< 600）SHALL 由上到下排列匯入區與已入庫頁面；平板與桌機左右並排（左邊匯入、右邊已入庫頁面）。顏色、字級、間距只用主題。

#### Scenario: 手機
- **WHEN** 寬度 400
- **THEN** 已入庫頁面在匯入區下方

#### Scenario: 桌機
- **WHEN** 寬度 1280
- **THEN** 已入庫頁面在匯入區右側

### Requirement: 參考畫面移除
`/proto/rules-ingest` SHALL 不再存在，即使開啟 `SHOW_PROTOTYPES` 也顯示找不到頁面。

#### Scenario: 開啟舊網址
- **WHEN** 開啟 `SHOW_PROTOTYPES` 並前往 `/proto/rules-ingest`
- **THEN** 顯示「找不到頁面」
