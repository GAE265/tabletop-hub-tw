## ADDED Requirements

### Requirement: 參考畫面只在開發版出現
`/proto/rules-ingest` MUST 只在 `SHOW_PROTOTYPES=true` 時註冊，只用 Flutter 預設元件，不調顏色、字型、間距，不需要 RWD。畫面不直接呼叫 API，所有操作都透過 `domains/rules_ingest/state/`。

#### Scenario: 開啟旗標
- **WHEN** 以 `SHOW_PROTOTYPES=true` 啟動並開啟 `/proto/rules-ingest`
- **THEN** 顯示輸入桌遊編號、選擇圖片、起始頁碼、匯入、讀回的元件

#### Scenario: 沒開旗標
- **WHEN** 沒有設定 `SHOW_PROTOTYPES` 並開啟 `/proto/rules-ingest`
- **THEN** 顯示「找不到頁面」

### Requirement: 逐頁匯入並顯示每頁結果
畫面 SHALL 讓使用者輸入 `games_id`、選擇一或多張圖片與起始頁碼（預設 1），按下匯入後依選取順序逐張呼叫匯入 API，頁碼從起始頁碼起每張加 1。每一頁 MUST 顯示頁碼、檔名與結果（成功或錯誤訊息）。某一頁失敗 MUST NOT 中止後面的頁面。

#### Scenario: 全部成功
- **WHEN** 選了 3 張圖片、起始頁碼 5，按下匯入，API 都回成功
- **THEN** 依序呼叫第 5、6、7 頁，結果列表三列都顯示成功

#### Scenario: 其中一頁失敗
- **WHEN** 三張圖片中第 2 張的 API 回 503
- **THEN** 第 1、3 張仍被送出，結果列表顯示第 2 頁的錯誤訊息，其他兩頁成功

#### Scenario: 匯入中
- **WHEN** 匯入進行中
- **THEN** 匯入按鈕不可再按，並顯示進行到第幾張、共幾張

#### Scenario: 欄位未填
- **WHEN** 沒有輸入 `games_id` 或沒有選任何圖片
- **THEN** 匯入按鈕不可按，不呼叫 API

#### Scenario: 無效的輸入
- **WHEN** `games_id` 不是正整數，或起始頁碼小於 1
- **THEN** 顯示欄位錯誤提示，不呼叫 API

### Requirement: 讀回已入庫頁面
畫面 SHALL 提供「讀回」操作，呼叫讀回 API 並列出每頁的頁碼與 Markdown 內容；匯入全部結束後 MUST 自動讀回一次。畫面 SHALL 顯示讀回回應中的 `ocr_provider`。

#### Scenario: 列出內容
- **WHEN** 輸入 `games_id` 後按下讀回，API 回兩頁
- **THEN** 依頁碼列出兩頁，每頁顯示頁碼與完整的 `content`（空字串顯示「（整頁沒文字）」）

#### Scenario: 匯入後自動讀回
- **WHEN** 一批匯入結束
- **THEN** 自動讀回並更新列表，使用者可以對照結果列表與資料庫內容

#### Scenario: 沒有資料
- **WHEN** 讀回的 `items` 為空
- **THEN** 顯示「這款桌遊還沒有規則書頁面」

#### Scenario: 顯示 OCR 實作
- **WHEN** 讀回回應的 `ocr_provider` 為 `fake`
- **THEN** 畫面顯示「OCR：fake（內容不是真實辨識結果）」；為 `cloud` 時顯示「OCR：cloud」

### Requirement: 載入與錯誤狀態
畫面 SHALL 對讀回與匯入顯示載入中與錯誤狀態，錯誤訊息使用後端回傳的 `error.message`。

#### Scenario: 讀回載入中
- **WHEN** 讀回請求尚未回應
- **THEN** 顯示載入指示

#### Scenario: 沒有權限
- **WHEN** 目前的開發身分是 `player`，API 回 403
- **THEN** 顯示後端的錯誤訊息，提示切換身分

#### Scenario: 桌遊不存在
- **WHEN** API 回 404 `GAME_NOT_FOUND`
- **THEN** 顯示後端的錯誤訊息，列表維持原狀不清空成功的紀錄
