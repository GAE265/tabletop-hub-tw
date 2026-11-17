# Design

## Context

- `rules_ingest`（瑋鋐）把規則書逐頁轉成 Markdown，存在 `games_manual(games_id, page, content)`。表屬於 `rules_ingest`，不是共用表；目前沒有切段、沒有向量（他的設計文件把 embedding 列為不做）。程式在 `feature/ocr` 分支，尚未合併。
- `ManualPagesService.list_pages(user, games_id)` 限 `shop_staff`、`admin`，是給 API 用的。
- 組內已自製規則教學影片：一款遊戲一支，目前 3 款有影片。影片放在哪裡尚未決定，本 change 只存網址。
- `integrations/llm` 有 `generate`、`generate_json`、`respond`（有狀態、靠 `previous_response_id` 接續對話）；`integrations/embedding` 有 `embed(texts)`。兩者都有 fake 實作。
- `games_advisor`（立倫）是現成的參考：`Vector()` 欄位、自己一組 `GAMES_ADVISOR_EMBEDDING_*` 設定、`POST /api/v1/advisor/messages` 的對話格式與錯誤碼。
- `games.id` 是 bigint（ADR 0003），參照它的表不可設定 cascade。

## Goals / Non-Goals

**Goals:**
- 有影片的遊戲先看影片再問；沒有影片的直接問。
- 答案只根據該款遊戲的規則書，並附上可以核對的頁碼。
- 可以連續追問。
- domain 測試全部使用 fake，不需要金鑰（AGENTS.md 7.6）。

**Non-Goals:**
- 影片的上傳、轉檔、代管。
- 規則書入庫（`rules_ingest` 負責）。
- 語音問答、AI 主持（#3 `host`）。
- 由 LLM 自動產生分段教學內容（之後可另開 change）。
- 自動偵測規則書更新後重建索引（本次用指令手動重建）。

## Decisions

**D1 問答只用規則書，影片只播放。**
問答的資料來源只有規則書頁面（切成段落存在 `rules_qa_chunks`），出處一律是頁碼。教學影片只存網址與標題，供教學頁播放。替代方案：同時從影片逐字稿找答案並引用時間點。被否決：使用者決定不需要從影片找答案，也省下逐字稿的製作與 WebVTT 解析。

**D2 資料表。**

`rules_qa_videos`（一款遊戲最多一支影片）：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `game_id` | bigint，主鍵，外鍵 `games.id`（不 cascade） | 這支教學影片教哪一款遊戲 |
| `video_url` | text | 影片網址（http／https） |
| `title` | text | 影片標題，顯示在教學頁 |
| `updated_at` | timestamptz | 最後一次設定的時間 |

`rules_qa_chunks`（檢索用的段落）：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid，主鍵 | |
| `game_id` | bigint，外鍵 `games.id`（不 cascade），有索引 | 段落屬於哪一款遊戲 |
| `page` | integer，CHECK `page >= 1` | 段落出自規則書第幾頁 |
| `content` | text | 段落文字 |
| `embedding` | vector | 向量；維度由設定決定，不寫死（4.4） |
| `embedding_model` | text | 產生向量的模型名稱；換模型時用來找出要重建的段落 |

`rules_qa_videos` 用 `game_id` 當主鍵而非 UUID：一款遊戲最多一支影片，`game_id` 本身就是唯一的識別（與 4.4「主鍵預設 UUID」不同，MR 說明要寫理由）。若 AGENTS.md 1.10 已合併，每個欄位加上 `comment=`。

**D3 切段方式。**
- 每頁依 Markdown 段落（空行）切開，再把相鄰段落合併到約 600 字以內；段落不跨頁，記錄頁碼。超過 600 字的單一段落依句號切開。

**D4 規則書頁面的讀取：在 `rules_ingest` 新增 service 方法。**
依 4.2，`rules_qa` 不能用 `games_manual` 的 model 或 repository。在 `ManualPagesService`（或另一個 service 函式）新增不檢查使用者的讀取方法（瑋鋐回覆查詢部分無法協助，由永傑新增，MR @ 瑋鋐審核），例如 `pages_for_game(games_id) -> list[(page, content)]`，只給後端指令與其他 domain 的 service 使用，不開放成 API。索引指令只由組員在後端執行，所以不需要使用者身分。
替代方案：請瑋鋐入庫時順便切段、轉向量。被否決：增加 `rules_ingest` 的範圍，而且檢索策略（切多大、存什麼出處）是問答的需求，應由 `rules_qa` 決定。

**D5 embedding 設定：`rules_qa` 自己一組。**
比照 `games_advisor`，新增 `RULES_QA_EMBEDDING_PROVIDER`、`_ENDPOINT`、`_API_KEY`、`_MODEL`、`_DIM`，沒填時用 fake，不退回其他 domain 的設定。理由：換模型時要重建索引，各 domain 各自控制比較安全。向量欄位維度讀 `RULES_QA_EMBEDDING_DIM`。瑋鋐（`integrations/` 擁有者）對此沒有表示意見，照本決定實作；若之後希望共用全域 `EMBEDDING_*`，只改設定來源，不影響其他設計。

**D6 問答流程。**
1. 確認遊戲存在（`core/games` 的 repository），沒有段落時回 409 `RULES_QA_NOT_READY`，不呼叫 LLM。
2. 把問題轉成向量，在 `rules_qa_chunks` 中只檢索該遊戲、`embedding_model` 符合目前設定的段落，依 cosine 距離取前 6 段。
3. 呼叫 `llm.respond(instructions, input, tools=[], output_schema, previous_response_id, allow_tool_calls=False)`。`input` 包含問題與編號過的段落；`output_schema` 為 `{answer, answerable, citation_ids}`，`citation_ids` 只能填段落編號。
4. 把 `citation_ids` 對回段落，轉成頁碼；不在這次檢索結果中的編號丟棄，同一頁只列一次，依頁碼排序。
5. 用語檢查：回答含「次」時，帶同一份段落與「不要使用『次』，改用局、輪、回合、階段、天」的指示要求改寫一次；仍有「次」時回 503 `RULES_QA_OUTPUT_REJECTED`。
6. 錯誤對應比照 `games_advisor`：`LLMConversationNotFound` → 404 `RULES_QA_CONVERSATION_NOT_FOUND`；`LLMUnavailable`、`EmbeddingError` → 503 `RULES_QA_UNAVAILABLE`。

每次追問都重新檢索，因為追問的主題可能換了；之前的對話內容由 LLM 端依 `previous_response_id` 保留。

**D7 instructions 的重點**（寫在 `rules_qa/prompts.py`）：只能根據提供的段落回答，找不到就說找不到並建議詢問店員；用繁體中文；依 AGENTS.md 10.2 使用局、輪、回合、階段、天，不使用「次」；回答簡短，條列步驟。

**D8 API 路徑。**
教學內容以遊戲為單位，資源名稱用 `rules-lessons`，以 `game_id` 識別：

| 方法與路徑 | 用途 | 權限 |
|---|---|---|
| `GET /api/v1/rules-lessons` | 有教材的遊戲清單 | 所有已登入角色 |
| `GET /api/v1/rules-lessons/{game_id}` | 教學內容 | 所有已登入角色 |
| `PUT /api/v1/rules-lessons/{game_id}/video` | 設定或取代影片網址與標題（整筆取代，所以用 PUT） | `shop_staff`、`admin` |
| `POST /api/v1/rules-lessons/{game_id}/messages` | 發問（新增一則訊息） | 所有已登入角色 |

設定影片權限比照 `rules_ingest` 的匯入：店家人員與管理員。遊戲不屬於某間店家，所以不檢查 `shop_id`。

**D9 前端影片播放。**
影片網址可能是自己代管的 mp4，也可能是 YouTube。建議用官方的 `video_player` 套件（支援 Web、Android、iOS），包在 `core/platform/` 的介面後面（5.3）。**新增套件需要組內同意**；如果影片放在 YouTube，`video_player` 不能播，需要改用其他套件或 iframe。這點要在 MR 2 開始前確定。

**D10 前端分層。**
- `data/`：freezed DTO（`RulesLessonSummary`、`RulesLesson`、`RulesAnswer`、`Citation`）與 `RulesQaRepository`、`HttpRulesQaRepository`。
- `state/`：`RulesLessonsNotifier`（清單）、`RulesLessonNotifier`（教學內容與「看完影片」狀態，family by `game_id`）、`RulesChatNotifier`（對話紀錄、`response_id`、送出中、錯誤，family by `game_id`）。播放器只在畫面中，state 只記錄「是否已看完影片、開始提問」。
- 參考畫面 `/proto/rules_qa`；正式頁面 `/rules`、`/rules/{game_id}`（go_router 子路由）。

**D11 測試。**
- service 單元測試：`FakeLLMProvider`（腳本化回應）、`FakeEmbeddingProvider`、手寫 `FakeRulesQaRepository`、`FakeManualPagesSource`（代替 `rules_ingest` 的 service）。
- API 測試連 `_test` 資料庫，使用 `as_player`、`as_shop_staff`、`as_admin`；向量用 fake embedding 產生的固定向量，確認「只檢索這款遊戲」與排序。
- 測試教材全部自行編寫（例如虛構的「測試桌遊」規則），不使用真實規則書全文。

**D12 拆成三個 MR。**
1. MR 1：後端（migration、索引指令、4 個 API）。需要 `feature/ocr` 先合併。
2. MR 2：前端 `data/`、`state/`、參考畫面、交接說明。
3. MR 3：正式頁面。

## Risks / Trade-offs

- **[依賴未合併的分支]** `games_manual` 還在 `feature/ocr`，而且建在訂位分支上，會跟訂位一起合併。→ MR 1 等它合併；在那之前可以先寫影片相關的部分與測試。
- **[只有影片、沒有規則書的遊戲]** 有影片的 3 款不一定都已入庫規則書。→ 教學頁照常播影片，問答區改顯示「規則書還沒入庫」；後端發問回 409 `RULES_QA_NOT_READY`。
- **[「次」的檢查太嚴]** 「其次」「次序」等詞也會被擋。→ 先嚴格執行，改寫一次通常能避開；若誤擋太多，再改成只檢查「第 N 次」「一次」等計數用法。
- **[檢索品質]** 段落大小、取幾段都是初始值。→ 寫成常數，之後依實際規則書調整；可以參考 `games_advisor` 的評估題組做法另開 change。
- **[索引與規則書不同步]** 規則書頁面重新入庫後，索引不會自動更新。→ 本次用指令手動重建，交接說明寫清楚；之後可請 `rules_ingest` 在匯入後呼叫 `rules_qa` 的 service。
- **[費用]** 建索引與問答都會呼叫雲端 embedding 與 LLM。→ 測試一律用 fake；索引只在教材更新時重建。

## Open Questions

1. 影片放在哪裡（自己代管的 mp4，或 YouTube）？這會決定 D9 的套件。`add-rules-video-maker` 產生的影片是 mp4，存在新增的 `integrations/storage`；若組內自製的影片也放在同一處，D9 就可以確定用 `video_player`。
2. 表名 `rules_qa_videos`、`rules_qa_chunks` 需要在群組告知（4.4）。
