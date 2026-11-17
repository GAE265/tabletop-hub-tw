# Proposal

## Why

功能 #2「規則教學與問答」目前完全沒有實作。玩家拿到一款沒玩過的桌遊時，需要兩件事：先看懂怎麼玩（教學），玩到一半有疑問時能馬上查到答案（問答），而且答案要有根據，不能是 AI 自己編的。

組內已經自製了規則教學影片（一款一支，目前 3 款有影片），規則書則由 `rules_ingest`（#5，瑋鋐）逐頁轉成文字存進 `games_manual`。本 change 把影片（教學）與規則書（問答）接起來：

- **有影片的遊戲**：先看教學影片，看完再發問。
- **沒有影片的遊戲**：直接發問。
- 問答的答案一律從規則書找，並附上出處（規則書第幾頁），玩家可以自己核對。影片只用來播放，不作為問答的資料來源。

## What Changes

- 新增 `rules_qa` domain 的後端：
  - `GET /api/v1/rules-lessons`：列出有教材（規則書或影片）的遊戲。
  - `GET /api/v1/rules-lessons/{game_id}`：某款遊戲的教學內容：影片（有的話）、是否有規則書、建議問題。
  - `PUT /api/v1/rules-lessons/{game_id}/video`：設定（或取代）某款遊戲的教學影片網址與標題。限店家人員與管理員。
  - `POST /api/v1/rules-lessons/{game_id}/messages`：規則問答。可以連續追問；每次都先從這款遊戲的規則書檢索相關段落，再交給 LLM 回答，並附上頁碼。
  - 後端指令：把某款遊戲的規則書頁面切段、轉成向量，建立檢索索引。
- 新增兩張資料表 `rules_qa_videos`、`rules_qa_chunks`（一個 migration）。
- 新增前端 `frontend/lib/domains/rules_qa/`：`data/`、`state/`、`prototypes/rules_qa/` 參考畫面、`pages/` 正式頁面，以及交接說明 `docs/handoff/rules_qa.md`。
- **不做**：從影片找答案（影片只播放）、影片的上傳與代管（只存網址，影片放在哪裡由組內決定）、語音問答（屬於 #3 AI 遊戲主持）、自動產生分段教學內容、規則書入庫本身（屬於 `rules_ingest`）。

## Capabilities

### New Capabilities
- `rules-qa`：規則教學與問答的後端行為（教學清單、教學內容、影片設定、規則書索引建立、問答與頁碼出處、用語規則、權限）。
- `rules-qa-page`：前端規則教學頁（遊戲清單、影片播放、問答對話、頁碼出處、各種狀態、RWD）。

### Modified Capabilities
無。

## Impact

- **受影響 domain**：`rules_qa`（主責永傑，協助新善、瑋鋐）。
- **相依的 domain**：`rules_ingest`（瑋鋐）。
  - 規則書頁面存在 `games_manual`，屬於 `rules_ingest`，不是共用表。依 AGENTS.md 4.2，`rules_qa` 只能呼叫 `rules_ingest` 的 service，不能直接用它的 model 或 repository。
  - 目前 `ManualPagesService.list_pages()` 限店家人員與管理員，是給 API 用的；索引指令需要一個不檢查使用者的讀取方法（見 design.md D4）。瑋鋐回覆查詢部分無法協助，由永傑新增，MR 要 @ 瑋鋐。
  - `rules_ingest` 的程式在 `feature/ocr` 分支，**尚未合併**；它建在訂位分支上，會跟 `booking` 一起合併。本 change 的 MR 1 要等它合併後才能開始。
- **共用資料表**：`games`（擁有者立倫）。`rules_qa_videos.game_id`、`rules_qa_chunks.game_id` 以外鍵參照 `games.id`（bigint），依 ADR 0003 不設定 cascade；遊戲名稱透過 `core/games` 的 repository 讀取，不改結構。
- **共用區**：
  - `backend/app/integrations/embedding/`、`integrations/llm/`（擁有者瑋鋐）：只使用既有介面，不修改。
  - `backend/app/core/config.py`、`.env.example`：新增 `RULES_QA_EMBEDDING_*` 設定（見 design.md D5），屬於立倫的共用區，MR 要 @ 立倫。
  - `backend/app/main.py`：掛載 router、建立 embedding provider，MR 要 @ 立倫。
  - `frontend/lib/app/router.dart`：新增路由，屬於永傑的共用區，主責本人修改。
- **契約**：有改動，新增上列 API（要 @ 立倫）。
- **migration**：一個，新增 `rules_qa_videos`、`rules_qa_chunks`（要 @ 瑋鋐）。建表前先在群組告知表名（4.4）。
- **新增套件**：前端播放影片可能需要 `video_player`（見 design.md D9，待確認）。
- **資料**：測試只用 `docs/samples/` 的片段或自行編寫的假資料，不提交規則書全文（AGENTS.md 第 2 節規則 2）。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
