# Spec Delta

## Purpose

`rules_qa` 後端：提供規則教學（教學影片＋建議問題）與規則問答。答案只能根據該款遊戲的規則書，並附上頁碼；教學影片只供播放，不作為問答的資料來源。規則書的檢索索引存在 `rules_qa_chunks`，影片資訊存在 `rules_qa_videos`。

術語依 AGENTS.md 第 10 節：一局（`match`）、一輪（`round`）、回合（`turn`）、階段（`phase`）、天（`day`）。教學與問答的回答不使用「次」。

## ADDED Requirements

### Requirement: 規則教學清單
`GET /api/v1/rules-lessons` SHALL 列出至少有一種教材（規則書索引或教學影片）的遊戲，每筆包含 `game_id`、`game_name`、`has_video`、`has_rulebook`，依遊戲名稱排序。所有已登入的角色都可以查詢。

#### Scenario: 列出有教材的遊戲
- **WHEN** 遊戲 1 有影片與規則書、遊戲 2 只有規則書、遊戲 3 只有影片、遊戲 4 都沒有
- **THEN** 回 200，`items` 有遊戲 1、2、3，`has_video`、`has_rulebook` 分別標示，沒有遊戲 4

#### Scenario: 還沒有任何教材
- **WHEN** 沒有任何遊戲有教材
- **THEN** 回 200，`items` 為空陣列

#### Scenario: 未登入
- **WHEN** `AUTH_MODE=jwt` 且沒有帶 token
- **THEN** 回 401

### Requirement: 教學內容
`GET /api/v1/rules-lessons/{game_id}` SHALL 回傳 `game_id`、`game_name`、`video`（`{video_url, title}`，沒有影片時為 `null`）、`has_rulebook`，以及固定的建議問題（例如「怎麼開始一局？」「一個回合可以做什麼？」「怎麼計分？」「遊戲什麼時候結束？」）。

#### Scenario: 有影片的遊戲
- **WHEN** 查詢有影片的遊戲
- **THEN** 回 200，`video` 有網址與標題，`suggested_questions` 不為空

#### Scenario: 沒有影片的遊戲
- **WHEN** 查詢只有規則書的遊戲
- **THEN** 回 200，`video` 為 `null`，`has_rulebook=true`

#### Scenario: 遊戲不存在
- **WHEN** `game_id` 在 `games` 找不到
- **THEN** 回 404，`GAME_NOT_FOUND`

#### Scenario: 遊戲存在但沒有教材
- **WHEN** 遊戲存在，但沒有規則書索引也沒有影片
- **THEN** 回 404，`RULES_LESSON_NOT_FOUND`

### Requirement: 設定教學影片
`PUT /api/v1/rules-lessons/{game_id}/video` SHALL 設定或取代該遊戲的教學影片（一款遊戲最多一支），body 為 `video_url`（http 或 https 網址）與 `title`。影片只供教學頁播放，不建立檢索索引。只有 `shop_staff` 與 `admin` 可以設定。

#### Scenario: 設定影片
- **WHEN** 管理員送出網址與標題
- **THEN** 回 200，回傳影片資料；之後教學內容的 `video` 為這支影片

#### Scenario: 取代既有影片
- **WHEN** 該遊戲已有影片，再送一次新的網址與標題
- **THEN** 回 200，影片資料被取代，該遊戲仍只有一支影片

#### Scenario: 網址或欄位格式錯誤
- **WHEN** `video_url` 不是 http／https 網址，或 `title` 為空
- **THEN** 回 422，資料不變

#### Scenario: 玩家沒有權限
- **WHEN** `player` 送出設定
- **THEN** 回 403

#### Scenario: 遊戲不存在
- **WHEN** `game_id` 在 `games` 找不到
- **THEN** 回 404，`GAME_NOT_FOUND`

### Requirement: 建立規則書索引
後端指令 SHALL 依 `game_id` 透過 `rules_ingest` 的 service 讀取規則書頁面，把每頁文字切成段落（段落不跨頁，記錄頁碼），轉成向量後，在同一個交易中取代該遊戲所有的段落。空白頁略過。指令可以重複執行，結果相同。

#### Scenario: 建立索引
- **WHEN** 遊戲 1 有 3 頁規則書，執行指令
- **THEN** `rules_qa_chunks` 有遊戲 1 的段落，每段都有頁碼與向量，指令印出建立的段落數

#### Scenario: 重新建立
- **WHEN** 規則書第 2 頁內容改了，再執行一次
- **THEN** 該遊戲舊的段落全部被取代，其他遊戲的段落不受影響

#### Scenario: 空白頁
- **WHEN** 某頁內容是空字串
- **THEN** 該頁不產生段落

#### Scenario: 沒有規則書
- **WHEN** 遊戲沒有任何規則書頁面
- **THEN** 指令不寫入，印出「這款遊戲還沒有規則書頁面」，以非 0 的結束碼結束

### Requirement: 規則問答
`POST /api/v1/rules-lessons/{game_id}/messages` SHALL 接收 `content`（去掉前後空白後 1–500 字）與 `previous_response_id`（必填欄位，新對話給 `null`），從**該遊戲**的規則書段落中檢索最相關的幾段，交給 LLM 回答，回傳 `response_id`、`answer`、`answerable`、`citations`。每個出處為 `{page}`（規則書頁碼），而且只能是這次檢索到的段落；同一頁只列一次，依頁碼排序；LLM 給出不在檢索結果中的出處時，SHALL 丟棄。所有已登入的角色都可以發問。

#### Scenario: 從規則書回答
- **WHEN** 問「一個回合可以做什麼？」，檢索到第 5 頁的段落
- **THEN** 回 201，`answerable=true`，`answer` 有內容，`citations` 包含 `{page: 5}`

#### Scenario: 引用同一頁的多個段落
- **WHEN** LLM 引用第 5 頁的兩個段落與第 3 頁的一個段落
- **THEN** `citations` 為 `[{page: 3}, {page: 5}]`

#### Scenario: 連續追問
- **WHEN** 帶上一則回應的 `response_id` 再問「那兩個人玩呢？」
- **THEN** LLM 收到同一個 `previous_response_id`，並且重新檢索這個新問題的段落

#### Scenario: 教材中找不到答案
- **WHEN** LLM 判斷檢索到的段落無法回答
- **THEN** 回 201，`answerable=false`，`citations` 為空，`answer` 說明規則書中找不到，建議詢問店員

#### Scenario: 只檢索這款遊戲
- **WHEN** 遊戲 1 與遊戲 2 都有段落，對遊戲 1 發問
- **THEN** 交給 LLM 的段落只來自遊戲 1

#### Scenario: 不給來源以外的出處
- **WHEN** LLM 回傳的出處有一個不在這次檢索結果中
- **THEN** 該出處被丟棄，其他出處保留

#### Scenario: 用語規則
- **WHEN** LLM 第一次回答使用了「次」
- **THEN** 後端以同一份段落要求 LLM 改寫一次；改寫後仍有「次」時回 503，`RULES_QA_OUTPUT_REJECTED`

#### Scenario: 還沒有規則書可以檢索
- **WHEN** 遊戲存在但沒有任何段落（例如只有影片、還沒入庫規則書）
- **THEN** 回 409，`RULES_QA_NOT_READY`，不呼叫 LLM

#### Scenario: 遊戲不存在
- **WHEN** `game_id` 在 `games` 找不到
- **THEN** 回 404，`GAME_NOT_FOUND`

#### Scenario: 問題格式錯誤
- **WHEN** `content` 去掉空白後是空字串、超過 500 字，或漏了 `previous_response_id` 欄位
- **THEN** 回 422，不呼叫 LLM

#### Scenario: LLM 無法使用
- **WHEN** LLM 或 embedding 服務無法連線
- **THEN** 回 503，`RULES_QA_UNAVAILABLE`（與推薦 Agent 的 `GAMES_ADVISOR_UNAVAILABLE` 一致）

#### Scenario: 對話已失效
- **WHEN** `previous_response_id` 在 LLM 那邊已經找不到
- **THEN** 回 404，`RULES_QA_CONVERSATION_NOT_FOUND`（與推薦 Agent 一致），前端應開始新對話
