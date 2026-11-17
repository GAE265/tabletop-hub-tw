# rules-qa-page Specification

## Purpose

前端規則教學頁：玩家選一款遊戲，有教學影片就先看影片，看完再發問；沒有影片就直接發問。答案一律來自規則書，下方列出頁碼。`prototypes/rules_qa/` 參考畫面與 `domains/rules_qa/pages/` 正式頁面共用同一份 `state/`。

畫面文字中的遊戲用語依 AGENTS.md 第 10.2 節，不使用「次」。

## Requirements

### Requirement: 遊戲清單
`RulesLessonsNotifier` SHALL 載入 `GET /api/v1/rules-lessons`，提供遊戲清單；每筆顯示遊戲名稱，有影片的遊戲標示「有教學影片」。

#### Scenario: 載入清單
- **WHEN** 開啟規則教學頁，後端回 2 款遊戲，其中 1 款有影片
- **THEN** 顯示 2 款遊戲，有影片的那款標示「有教學影片」

#### Scenario: 沒有任何教材
- **WHEN** 後端回空清單
- **THEN** 顯示「目前還沒有可以教學的遊戲」

#### Scenario: 載入中與失敗
- **WHEN** API 尚未回應，或回錯誤
- **THEN** 分別顯示載入中，或錯誤訊息與「重試」按鈕

### Requirement: 教學頁
選一款遊戲後，`RulesLessonNotifier` SHALL 載入 `GET /api/v1/rules-lessons/{game_id}`。有影片時，頁面先顯示影片播放器（`source=youtube` 用 YouTube 播放器；`source=file` 的 mp4 由 `add-rules-video-maker` 加上支援）與「看完了，開始提問」按鈕，按下後才顯示問答區；沒有影片時，直接顯示問答區與建議問題。

#### Scenario: 有影片
- **WHEN** 開啟有 YouTube 影片的遊戲
- **THEN** 頁面內嵌 YouTube 播放器（用 `youtube_id`），顯示「看完了，開始提問」，問答區尚未顯示

#### Scenario: 看完影片開始提問
- **WHEN** 按「看完了，開始提問」
- **THEN** 顯示問答區與建議問題，影片仍可以繼續看

#### Scenario: 沒有影片
- **WHEN** 開啟只有規則書的遊戲
- **THEN** 不顯示播放器，直接顯示問答區、建議問題與「這款遊戲還沒有教學影片，可以直接問規則」

#### Scenario: 只有影片、還沒有規則書
- **WHEN** 開啟 `has_rulebook=false` 的遊戲
- **THEN** 可以看影片，但不顯示問答區，改顯示「這款遊戲的規則書還沒入庫，暫時無法提問」

#### Scenario: 遊戲沒有教材
- **WHEN** API 回 404 `RULES_LESSON_NOT_FOUND`
- **THEN** 顯示後端的錯誤訊息與「回到遊戲清單」

### Requirement: 問答
`RulesChatNotifier` SHALL 送出 `POST /api/v1/rules-lessons/{game_id}/messages`，保存上一則回應的 `response_id` 供追問使用，並依序保留對話紀錄。每則回答下方列出出處，顯示「規則書第 N 頁」。

#### Scenario: 發問並得到答案
- **WHEN** 輸入「怎麼計分？」並送出，後端回答並引用第 12 頁
- **THEN** 對話紀錄依序出現問題與回答，回答下方顯示「規則書第 12 頁」

#### Scenario: 點建議問題
- **WHEN** 點建議問題「一個回合可以做什麼？」
- **THEN** 直接以該文字送出

#### Scenario: 追問
- **WHEN** 已有一則回答，再送出下一個問題
- **THEN** 請求帶上一則回答的 `response_id`

#### Scenario: 找不到答案
- **WHEN** 後端回 `answerable=false`
- **THEN** 顯示回答內容，不顯示出處

#### Scenario: 開始新對話
- **WHEN** 按「開始新對話」
- **THEN** 清空對話紀錄，下一個問題的 `previous_response_id` 為 `null`

#### Scenario: 對話已失效
- **WHEN** 後端回 404 `RULES_QA_CONVERSATION_NOT_FOUND`
- **THEN** 顯示「對話已過期，已為你開始新對話」，清空 `response_id`，保留輸入框中的問題讓玩家重送

#### Scenario: 送出中
- **WHEN** 已送出、API 尚未回應
- **THEN** 送出按鈕與建議問題停用，顯示「正在查規則…」，不能重複送出

#### Scenario: 送出失敗
- **WHEN** API 回 503 或無法連線
- **THEN** 顯示後端的錯誤訊息，問題保留在輸入框，可以重送

#### Scenario: 空白問題
- **WHEN** 輸入框是空白
- **THEN** 送出按鈕停用

### Requirement: RWD 與路由
正式頁面路由為 `/rules`（遊戲清單）與 `/rules/{game_id}`（教學頁）；參考畫面為 `/proto/rules_qa`（只有 `SHOW_PROTOTYPES=true` 時註冊）。手機版影片在上、問答在下；平板與桌機影片與問答左右並排。正式頁面 MUST NOT 寫死顏色、字級、間距。

#### Scenario: 手機寬度
- **WHEN** 視窗寬度 < 600
- **THEN** 影片在上、問答在下，沒有水平捲軸

#### Scenario: 桌機寬度
- **WHEN** 視窗寬度 >= 1024，且遊戲有影片
- **THEN** 影片與問答左右並排

#### Scenario: 參考畫面只在開發版出現
- **WHEN** `SHOW_PROTOTYPES` 不是 `true`
- **THEN** `/proto/rules_qa` 不存在，`/rules` 仍可使用
