# spec：桌遊推薦 Agent + 桌遊 RAG（games_advisor）

- Map：[桌遊推薦 Agent + 桌遊 RAG](map.md)
- 狀態：前半（共用部分、桌遊資料與心得管線）2026-11-08、後半（推薦對話與 API）2026-11-09 立倫看過。2026-11-10 補上外部服務測試（§2、§17、§18）；同日依 AGENTS.md 7.6（#18）改用 `external` 標記。2026-11-11 資料表改版：桌遊改成共用表 `games`、新增類型、心得摘要搬到自己的表（§3，〔改表〕、ADR 0003）。2026-11-12 `games.id` 改成整數、自動給號，其他組員用匯出檔同步（§3、§8.1、§8.10、§8.11，〔整數編號〕）。2026-11-13 依 AGENTS.md 1.8：類型的兩張表改名為 `genres`、`game_genres`，`genres.id` 改成流水號，共用表不再是例外，只剩 `games.id` 是例外（§3，〔1.8〕）。2026-11-14 評估題組加上 LLM 評審建議，不算分（§15.1、§15.3、§15.4、§15.6，〔評審〕）。
- 這份 spec 只整理已定案的決定，不重新決定。標〔Qn〕的地方是寫 spec 時發現的缺漏：Q1–Q8 記在「[spec：桌遊資料與心得管線](issues/20-spec-data-and-review-pipeline.md)」的 Comments，Q9 起記在「[spec：推薦對話與 API](issues/21-spec-conversation-and-api.md)」的 Comments。

## 怎麼讀

每條規則後面的〔 〕是出處。前後 ticket 說法不同時，以 map 的 Decisions so far 標示的更正為準。

| 標記 | 出處 |
|---|---|
| 〔收錄〕 | [收錄哪些桌遊、存哪些欄位](issues/06-game-coverage-and-fields.md) |
| 〔資料來源〕 | [桌遊基本資料從哪裡取得](issues/02-game-data-sources.md) |
| 〔心得來源〕 | [心得來源走哪條路](issues/16-review-source-decision.md) |
| 〔詞彙表〕 | [標籤詞彙表怎麼定](issues/08-tag-vocabulary.md) |
| 〔管線〕 | [心得怎麼變成標籤](issues/09-review-to-tags-pipeline.md) |
| 〔比對〕 | [條件與偏好怎麼比對桌遊](issues/10-matching-strategy.md) |
| 〔改版〕 | [詞彙表改版或換 embedding 模型時怎麼處理](issues/18-vocabulary-and-embedding-revisions.md) |
| 〔LLM 設定〕 | [LLM 設定也改成 games_advisor 自己的一組嗎](issues/19-games-advisor-llm-settings.md) |
| 〔部署〕 | [專題專用 Foundry 要部署哪些模型](issues/17-foundry-model-deployments.md) |
| 〔驗收〕 | [怎麼驗收推薦結果](issues/14-recommendation-acceptance.md) |
| 〔API〕 | [API 契約與 prototype 頁面](issues/13-api-contract-and-prototype.md) |
| 〔理由〕 | [推薦理由要寫什麼、要不要附出處](issues/11-recommendation-reasons.md) |
| 〔流程〕 | [Agent 怎麼追問、什麼時候推薦](issues/07-conversation-flow.md) |
| 〔ADR 0001〕 | [games_advisor 的對話狀態交給 Azure Responses API 保存](../../docs/adr/0001-games-advisor-conversation-state-in-azure.md)（accepted） |
| 〔ADR 0002〕 | [games_advisor 的追問與推薦由 LLM 依對話規則決定](../../docs/adr/0002-games-advisor-llm-driven-conversation-flow.md)（accepted） |
| 〔ADR 0003〕 | [桌遊基本資料改成所有 domain 共用的 `games` 表](../../docs/adr/0003-shared-games-table.md)（accepted） |
| 〔改表〕 | 2026-11-11 資料表改版的決定，記在「[把 spec 拆成 TDD 實作 ticket](issues/22-split-spec-into-tdd-tickets.md)」的 Comments |
| 〔整數編號〕 | 2026-11-12 `games.id` 改成整數、自動給號，其他組員用匯出檔同步的決定：組員在 [MR #22](https://github.com/GAE265/tabletop-hub-tw/pull/22) 提出，立倫 grilling 後定案，記在〔ADR 0003〕 |
| 〔1.8〕 | 2026-11-13 對齊 AGENTS.md 1.8（[MR #23](https://github.com/GAE265/tabletop-hub-tw/pull/23)）：第 3 節「共用資料表」清單、§4.2 共用表的 repository、§4.4 主鍵預設 UUID 與分類表可用流水號 |
| 〔評審〕 | 2026-11-14 評估題組加上 LLM 評審建議的決定，記在「[怎麼驗收推薦結果](issues/14-recommendation-acceptance.md)」的 Comments |
| 〔提案 §n〕 | [整合層提案](integrations-proposal.md)第 n 節 |
| 〔map〕 | map 的 Notes（固定偏好）與 Out of scope |
| 〔Qn〕 | 寫 spec 時發現的缺漏，由立倫決定。Q1–Q8 見「[spec：桌遊資料與心得管線](issues/20-spec-data-and-review-pipeline.md)」的 Comments；Q9 起見「[spec：推薦對話與 API](issues/21-spec-conversation-and-api.md)」的 Comments |

§n 指該 ticket Answer 的第 n 點。

---

# 共用部分

## 1. 目的

推薦 Agent 和玩家多輪對話，問出條件與偏好，從收錄的桌遊中推薦最多 3 款，每款附推薦理由，理由引用心得片段。

- 主要展示 Agent 與桌遊 RAG 的應用，準確率不追求最高。〔驗收〕〔map〕
- 桌遊基本資料（`games`）與類型是所有 domain 共用的表，用來統一桌遊的編號與名稱；心得摘要、標籤、心得片段只供推薦使用。〔改表〕、〔ADR 0003〕（推翻〔map〕原本「不給其他 domain 參照」的決定）
- 推薦（「查桌遊」工具、API、評估題組）先不用類型：這次只建表、存資料，之後再談。〔改表〕
- 不在範圍：正式頁面（永傑依交接說明製作，AGENTS.md §5.4）、店家有沒有這款桌遊、地端 LLM、語音對話。〔map〕

**需求 2 的說明**（MR 說明也用這段）〔心得來源〕§8：

> 心得由 Codex 用網路搜尋收集，每款 2–5 篇，中英文都有，存在 repo 外；後端不寫爬蟲，只讀 Codex 產生的檔案、產生標籤。

### 1.1 程式放哪裡

| 部分 | 位置 |
|---|---|
| 後端 | `backend/app/domains/games_advisor/`：`router`、`schemas`、`service`、`repository`、`models`（AGENTS.md §4.1），加上一個批次指令模組（§7）〔管線〕§8 |
| 共用桌遊表 | `backend/app/core/games/`：`games`、`genres`、`game_genres` 的資料表定義與 `GameRepository`（共用表只有這一個 repository，AGENTS.md §4.2），負責人立倫（§3、〔ADR 0003〕、〔1.8〕） |
| 整合層 | `backend/app/integrations/llm/`、`integrations/embedding/`（瑋鋐擁有），介面照[整合層提案](integrations-proposal.md) |
| 測試 | `backend/tests/games_advisor/` |
| 前端 | `frontend/lib/domains/games_advisor/` 的 `data/`、`state/`，`frontend/lib/prototypes/games_advisor/`，交接說明 `docs/handoff/games_advisor.md`（§14） |

## 2. 術語

用 `GLOSSARY.md` 提案區的定義，這裡不重寫：條件、偏好、標籤、標籤詞彙表、信心分數、類型、類別、機制、難度、心得、心得摘要、心得片段、對話、訊息、推薦 Agent、推薦、推薦理由、追問。

本 spec 另外用到的開發用語，不放進 `GLOSSARY.md`：

| 用語 | 意思 | 出處 |
|---|---|---|
| 批次指令 | `games_advisor` 在本機手動執行的後端指令：匯入桌遊、心得管線、評估題組 | 〔管線〕§8 |
| 評估題組、評估題 | 用真的模型檢查推薦品質的題目，不進 CI、不擋合併 | 〔驗收〕§2 |
| 詞彙表草稿、歸納報告、標籤草稿 | 批次指令產生、給立倫審核的檔案（§5） | 〔管線〕§1、§4 |
| 外部服務測試 | `integrations/` 裡要讀 `.env` 的金鑰、連到真的外部服務（例如 Azure）的 pytest。加上 `external` 標記，不在 CI 跑；改到 `integrations/` 的 MR，發 MR 前在本機執行 `uv run pytest -m external`，結果貼在 MR 說明。評估題組是指令，不算這類測試 | AGENTS.md 7.6 |

## 3. 資料表總覽

7 張表，分成兩組，放在同一個 migration（§3.8）。〔改表〕

| 組 | 表 | 誰負責 | 程式位置 |
|---|---|---|---|
| 共用表 | `games`、`genres`、`game_genres` | 立倫 | `backend/app/core/games/` |
| games_advisor | `games_advisor_review_summaries`、`games_advisor_tags`、`games_advisor_game_tags`、`games_advisor_review_excerpts` | 立倫 | `backend/app/domains/games_advisor/` |

- **共用表照 AGENTS.md 第 3 節「共用資料表」的規則**（〔1.8〕、〔ADR 0003〕）：表名不用 domain 名稱開頭；一張表只有一個 model 與一個 repository，放在 `backend/app/core/games/`，各 domain 的 service 可以直接使用（AGENTS.md §4.2）。只有 games_advisor 的匯入桌遊（立倫執行）與同步（其他組員執行）兩個指令寫入共用表。〔整數編號〕
- **唯一的例外是 `games.id`**：AGENTS.md §4.4 規定主鍵預設是 UUID，只有固定的小型分類表可以用流水號。`games.id` 是整數（bigint）、自動給號，2026-11-13 立倫確認瑋鋐同意以例外處理（〔ADR 0003〕）。
- 其他主鍵：`genres.id` 是流水號（bigint；固定的小型分類表，§4.4 允許）；其餘都是 UUID 的 `id`，預設 `gen_random_uuid()`（比照 `0001_baseline`）。games_advisor 的表名以 `games_advisor_` 開頭；參照欄位叫 `<對象>_id`。〔1.8〕
- 向量欄位的長度讀 `GAMES_ADVISOR_EMBEDDING_DIM`，不寫死。〔改版〕§6
- 不建向量索引：資料量小，逐筆比對就夠快，結果也精確。〔比對〕§7

### 3.1 `games`：桌遊，一款一列（共用）

| 欄位 | 型別 | 可為空 | 說明 | 出處 |
|---|---|---|---|---|
| `id` | bigint，主鍵，自動給號 | 否 | 桌遊編號 1、2、3……。立倫匯入時由資料庫自動給號，1–4 號固定（見下方）；其他組員同步時照匯出檔的編號寫入（§8.11），所以每個人的編號都一樣。只能是正整數；給出去就不改、不重複使用，刪掉的編號空著 | 〔改表〕、〔整數編號〕 |
| `bgg_id` | integer，不重複 | 否 | BGG 的編號。Demo 遊戲都查到了：血與刃的白薔薇 400566、阿不思學院 144734、馬可波羅 171623（03） | 〔收錄〕§4 |
| `name` | text | 否 | 繁中名稱，立倫手填 | 〔收錄〕§2 |
| `english_name` | text | 否 | 英文名稱，BGG 的主要名稱 | 〔收錄〕§2、〔改表〕 |
| `min_players`、`max_players` | integer | 否 | 人數 | 〔收錄〕§2、〔比對〕§1 |
| `min_playtime`、`max_playtime` | integer | 否 | 時長（分鐘） | 同上 |
| `min_age` | integer | 否 | 最低年齡 | 同上 |
| `weight` | double precision | 否 | 難度 1–5，BGG `averageweight` 的原值 | 〔收錄〕§2 |
| `categories` | text[] | 否 | 類別，BGG 英文名稱；可以是空陣列 | 〔收錄〕§2；存法〔Q2〕 |
| `mechanics` | text[] | 否 | 機制，BGG 英文名稱；可以是空陣列 | 同上 |

- 數值範圍照 §8.1 的檢查，也寫成資料庫的 check 限制。
- 1–4 號固定是 4 款 Demo 遊戲，匯入時用 `--first-four` 指定（§8.1）：〔整數編號〕

  | `id` | 桌遊 | `bgg_id` |
  |---|---|---|
  | 1 | 血與刃的白薔薇 | 400566 |
  | 2 | 阿不思學院 | 144734 |
  | 3 | 馬可波羅 | 171623 |
  | 4 | 阿瓦隆 | 128882 |

- `id` 用 `GENERATED BY DEFAULT AS IDENTITY`：寫入時沒給 `id` 就自動給下一個號碼；給了就照給的寫入（同步要用）。下一個號碼記在資料庫的計數器（sequence），照給的寫入不會推動計數器，所以同步要照匯出檔設定它（§8.11）。〔整數編號〕
- 不存：簡介、圖片、價格、評分與排名、最佳人數。〔收錄〕§2
- API 卡片的 `game` 物件沿用這些欄位名稱（`id`、`name`、`min_players`、`max_players`、`min_playtime`、`max_playtime`、`min_age`、`weight`）。〔API〕§1

### 3.2 `genres`：類型，8 列（共用）

| 欄位 | 型別 | 可為空 | 說明 |
|---|---|---|---|
| `id` | bigint，主鍵，自動給號 | 否 | 流水號。找類型一律用 `code`，程式、種子資料與測試都不寫死 `id`（AGENTS.md §4.4）〔1.8〕 |
| `code` | text，不重複 | 否 | 英文代碼 |
| `name` | text，不重複 | 否 | 繁中名稱 |

8 列由 migration 寫入（固定的分類，不是測試帳號，所以不違反 AGENTS.md §4.4「測試帳號不寫進 migration」）：

| `code` | `name` |
|---|---|
| `party` | 派對 |
| `strategy` | 策略 |
| `thematic` | 主題 |
| `war` | 戰爭 |
| `abstract` | 抽象 |
| `customizable` | 集換 |
| `children` | 孩童 |
| `family` | 家庭 |

- 類型和類別是兩回事：類型只有這 8 個，類別是 BGG 的細分類（術語見 `GLOSSARY.md`）。〔改表〕
- 推薦（「查桌遊」工具、API、評估題組）先不用類型，之後再談（§1）。

### 3.3 `game_genres`：每款桌遊的類型（共用）

| 欄位 | 型別 | 可為空 | 說明 |
|---|---|---|---|
| `id` | uuid，主鍵 | 否 | |
| `game_id` | bigint，參照 `games.id` | 否 | 桌遊被刪除時，這一列跟著刪 |
| `genre_id` | bigint，參照 `genres.id` | 否 | |

- 一款桌遊可以有多個類型，也可以沒有：`(game_id, genre_id)` 不重複。〔改表〕
- 匯入桌遊時照 `games.json` 的 `types` 整組替換（§8.1）。

### 3.4 `games_advisor_review_summaries`：心得摘要，一款最多一列

| 欄位 | 型別 | 可為空 | 說明 | 出處 |
|---|---|---|---|---|
| `id` | uuid，主鍵 | 否 | | AGENTS.md §4.4 |
| `game_id` | bigint，參照 `games.id`，不重複 | 否 | 桌遊被刪除時，這一列跟著刪 | 〔改表〕 |
| `summary` | text | 否 | 心得摘要 | 〔比對〕§7、〔管線〕§5 |
| `embedding` | vector(`GAMES_ADVISOR_EMBEDDING_DIM`) | 否 | 心得摘要向量 | 〔比對〕§7、〔改版〕§6 |
| `embedding_model` | text | 否 | 產生向量時的 `GAMES_ADVISOR_EMBEDDING_MODEL`；fake 記 `fake` | 〔改版〕§5 |

- 原本放在桌遊表的 3 個欄位，因為 `games` 改成共用表而搬到這裡：只有推薦用得到。〔改表〕
- 摘要、向量、模型名稱在同一列，一起寫入；清空心得摘要就是刪掉這一列。匯入桌遊不碰這張表。

### 3.5 `games_advisor_tags`：標籤詞彙表

| 欄位 | 型別 | 可為空 | 說明 | 出處 |
|---|---|---|---|---|
| `id` | uuid，主鍵 | 否 | | AGENTS.md §4.4 |
| `code` | text，不重複 | 否 | 英文代碼，符合 `^[a-z][a-z0-9_]*$` | 〔管線〕§1、§9 |
| `name` | text，不重複 | 否 | 繁中名稱 | 〔詞彙表〕§2、〔管線〕§1 |
| `definition` | text | 否 | 繁中定義，一句 | 〔詞彙表〕§2 |

- 一列是一個標籤，每個標籤只出現一次。哪款桌遊有哪個標籤存在 §3.6，兩張表的關係和 `genres`、`game_genres` 相同。
- 正本是 repo 裡的 `tag_vocabulary.json`；資料表是同步出來的副本，因為「查桌遊」工具的 enum 從資料庫產生。〔管線〕§1
- 不記錄詞彙表版本。〔改版〕總覽

### 3.6 `games_advisor_game_tags`：每款桌遊的標籤

| 欄位 | 型別 | 可為空 | 說明 | 出處 |
|---|---|---|---|---|
| `id` | uuid，主鍵 | 否 | | AGENTS.md §4.4 |
| `game_id` | bigint，參照 `games.id` | 否 | 桌遊被刪除時，這一列跟著刪 | 〔管線〕§9、〔改表〕 |
| `tag_id` | uuid，參照 `games_advisor_tags.id` | 否 | 標籤被刪除時，這一列跟著刪 | 〔管線〕§9、〔改版〕§1 |
| `confidence` | double precision | 否 | 信心分數 0–1 | 〔詞彙表〕§4 |

- 同一款的同一個標籤只有一列：`(game_id, tag_id)` 不重複。〔管線〕§9
- 低於門檻 0.5 的標籤也存，推薦時才套用門檻。〔管線〕§2
- 標籤依據的心得網址不存，只在標籤草稿裡。〔管線〕§4

### 3.7 `games_advisor_review_excerpts`：心得片段

| 欄位 | 型別 | 可為空 | 說明 | 出處 |
|---|---|---|---|---|
| `id` | uuid，主鍵 | 否 | 推薦理由引用的片段 ID | AGENTS.md §4.4、〔理由〕 |
| `game_id` | bigint，參照 `games.id` | 否 | 桌遊被刪除時，這一列跟著刪 | 〔管線〕§9、〔改表〕 |
| `text` | text | 否 | 片段原文，不翻譯 | 〔管線〕§6 |
| `embedding` | vector(`GAMES_ADVISOR_EMBEDDING_DIM`) | 否 | 片段向量 | 〔比對〕§7、〔改版〕§6 |
| `embedding_model` | text | 否 | 產生向量時的 `GAMES_ADVISOR_EMBEDDING_MODEL`；fake 記 `fake` | 〔改版〕§5 |
| `source_url` | text | 否 | 從所屬心得複製 | 〔心得來源〕§5 |
| `site_name` | text | 否 | 從所屬心得複製 | 〔心得來源〕§5 |
| `language` | text | 否 | `zh-TW` 或 `en`，從所屬心得複製 | 〔心得來源〕§5 |

- 不加 `title`、`author`、`published_on`。「推薦理由要寫什麼、要不要附出處」原本要加 `title`，已由〔API〕§7 更正。
- `source_url`、`site_name` 只留在資料庫方便查證，API 不回。〔API〕§7
- 片段和向量在同一個交易寫入，所以向量不會是空的；改維度時整列刪掉重產。〔改版〕§6

### 3.8 migration

- 7 張表放在同一個 migration，由 05 建立；一個 MR 最多一個 migration，由瑋鋐審核（AGENTS.md §4.4）。〔改表〕
- 建立向量欄位的 migration 從 `GAMES_ADVISOR_EMBEDDING_DIM` 讀維度。〔改版〕§6
- 改維度用的 migration 現在不寫：large 縮成 1536 維，換成 small 也是 1536 維。〔改版〕§6

migration 的測試（比照 `tests/migrations/test_baseline.py`）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 空資料庫，`GAMES_ADVISOR_EMBEDDING_DIM` 沒填 | `alembic upgrade head` | 7 張表都在；兩個向量欄位都是 1536 維；`games.id`、4 個 `game_id` 欄位、`genres.id`、`game_genres.genre_id` 都是 bigint |
| `GAMES_ADVISOR_EMBEDDING_DIM=8` | 同上 | 兩個向量欄位都是 8 維 |
| 空資料庫 | `alembic upgrade head` | `genres` 有 8 列，代碼與名稱照 §3.2 |
| 新增一個類型，不給 `id` | 寫入 | 自動給號，和原本 8 個不重複〔1.8〕 |
| 寫入兩款桌遊，不給 `id` | 寫入 | 自動拿到 1、2 |
| 寫入一款桌遊，`id` 給 5 | 寫入 | 成功，`id` 是 5 |
| `games.id` 寫入 `"a"` | 寫入 | 資料庫拒絕（型別不對） |
| `games.id` 寫入 0、-1 | 寫入 | 資料庫拒絕（只能是正整數） |
| 已經 upgrade | `alembic downgrade` 回前一版 | 7 張表都移除 |

05 另外補的測試（2026-11-12 立倫同意）：`bgg_id` 不重複；同一款桌遊的類型、標籤不重複，心得摘要最多一列；刪桌遊時類型、心得摘要、標籤、心得片段一起刪；刪標籤時每款桌遊上的這個標籤一起刪。〔整數編號〕

## 4. 設定欄位總覽

### 4.1 `.env`

| 欄位 | 預設 | 用途 | 出處 |
|---|---|---|---|
| `LLM_PROVIDER` | `fake` | `fake`、`cloud`（Azure OpenAI）、`local`（尚未實作） | 〔提案 §7〕、〔LLM 設定〕§1 |
| `LLM_ENDPOINT` | — | v1 端點，`https://<資源名稱>.openai.azure.com/openai/v1/` | 〔提案 §7〕 |
| `LLM_API_KEY` | — | 既有欄位 | 〔提案 §7〕 |
| `LLM_MODEL` | — | 對話模型的部署名稱；`LLM_BATCH_MODEL` 留空時，批次指令也用它 | 〔提案 §7〕 |
| `LLM_BATCH_MODEL` | 空 | 批次指令的部署名稱 | 〔部署〕§2 |
| `LLM_REASONING_EFFORT` | 空（用模型預設） | `none`、`low`、`medium`、`high`、`xhigh`、`max`；不是合法值就啟動失敗；批次指令不帶 | 〔部署〕§4、〔提案 §7〕 |
| `LLM_TIMEOUT_SECONDS` | 30 | 對話的單次請求逾時；批次指令固定 300 秒，不讀這個欄位 | 〔部署〕§6 |
| `GAMES_ADVISOR_EMBEDDING_PROVIDER` | `fake` | `fake`、`cloud` | 〔改版〕§4 |
| `GAMES_ADVISOR_EMBEDDING_ENDPOINT` | — | 目前和 `LLM_ENDPOINT` 填一樣的值 | 〔改版〕§4、〔提案 §7〕 |
| `GAMES_ADVISOR_EMBEDDING_API_KEY` | — | | 〔改版〕§4 |
| `GAMES_ADVISOR_EMBEDDING_MODEL` | — | embedding 的部署名稱；也記在每個向量上 | 〔改版〕§4、§5 |
| `GAMES_ADVISOR_EMBEDDING_DIM` | 1536 | 向量長度，也是向量欄位的維度 | 〔改版〕§4、§6 |

- LLM 用全域 `LLM_*`，只有 embedding 是 `games_advisor` 自己的一組。〔LLM 設定〕§1
- `GAMES_ADVISOR_EMBEDDING_*` 沒填時不退回任何全域設定。組員與 CI 不用填，預設就是 fake。〔改版〕§4
- 全域的 `EMBEDDING_DIM` 保留不動，`games_advisor` 不讀它。〔改版〕§4
- `core/config.py` 與 `.env.example` 由立倫加欄位；`.env.example` 只寫欄位名與說明（AGENTS.md §2.1）。〔提案 §7〕

立倫自己的 `.env`（不寫金鑰與真實資源名稱）〔部署〕；embedding 的欄位名稱照〔改版〕更正：

```
LLM_PROVIDER=cloud
LLM_ENDPOINT=https://<資源名稱>.openai.azure.com/openai/v1/
LLM_MODEL=gpt-5.6-luna
LLM_BATCH_MODEL=gpt-5.6-terra
LLM_REASONING_EFFORT=low
LLM_TIMEOUT_SECONDS=30
GAMES_ADVISOR_EMBEDDING_PROVIDER=cloud
GAMES_ADVISOR_EMBEDDING_ENDPOINT=（和 LLM_ENDPOINT 相同）
GAMES_ADVISOR_EMBEDDING_MODEL=text-embedding-3-large
GAMES_ADVISOR_EMBEDDING_DIM=1536
```

### 4.2 程式裡的常數

前面 ticket 把下面這些值稱為「設定值」。寫成程式常數，集中在 `games_advisor` 的一個檔案，不開 `.env` 欄位。〔Q1〕

- 本機改常數做實驗，不用開 MR。
- 要合併進 `dev` 時照常走 MR，因為 AGENTS.md §8.1 不准直接推到 `dev`。改到排序用的值（門檻、片段數、RRF 的 k）時，把評估題組的分數貼進 MR。〔驗收〕§3

| 值 | 預設 | 用在 | 出處 |
|---|---|---|---|
| 詞彙表標籤數上限 | 30 | 同步詞彙表 | 〔管線〕§1 |
| 信心分數門檻 | 0.5 | 查桌遊（§11） | 〔管線〕§2 |
| 心得片段最短 | 40 個中文字／25 個英文單字 | 產生心得片段 | 〔管線〕§6 |
| 心得片段最長 | 300 個中文字／150 個英文單字 | 產生心得片段 | 〔管線〕§6 |
| 每款回傳的心得片段數 | 2 | 查桌遊（§11） | 〔比對〕§6 |
| RRF 的 k | 60 | 查桌遊（§11） | 〔比對〕§5 |

批次指令的 LLM 逾時 300 秒已定為寫在指令裡、不開設定〔部署〕§6，不在這張表的問題範圍。

## 5. 檔案總覽

| 檔案 | 位置 | 進 repo | 誰寫 | 誰讀 |
|---|---|---|---|---|
| `games.json` | repo 外的團隊資料夾，臨時 | 否 | Codex（繁中名稱由立倫手填） | 匯入桌遊（立倫執行一次，之後可以刪掉）；Codex 收心得時也讀 |
| 匯出檔 | 團隊共用雲端資料夾 GAE265G5，只放最新的一份 | 否 | 立倫執行匯出（§8.10） | 其他組員執行同步（§8.11）；立倫重建資料庫時也讀 |
| `reviews.json` | 和 `games.json` 同一個資料夾 | 否 | Codex | 心得管線的各個指令 |
| `tag_vocabulary.json` | `backend/app/domains/games_advisor/tag_vocabulary.json`〔Q7〕 | 是 | 歸納指令產生草稿，立倫編輯後走 MR | 同步詞彙表；評估題組的 pytest |
| 歸納報告 | repo 外，`--report` 指定 | 否（含心得網址） | 歸納詞彙表 | 立倫 |
| 標籤草稿 | repo 外，`--out` 指定 | 否 | 上標籤 | 立倫刪標籤後，匯入標籤草稿讀回 |
| `eval_cases.json` | `backend/tests/games_advisor/` | 是 | 立倫 | 評估題組（§15） |
| 評估報告 | repo 外，`--out` 指定 | 否（含心得片段原文） | 評估題組 | 立倫（§15.4） |

- 心得只存在 `reviews.json`，不進 repo、不存進資料庫。資料庫只存從心得產生的資料；心得片段存原文，但資料庫不是 repo。〔心得來源〕§5
- 測試只用自編的假桌遊與假心得（AGENTS.md §2.2、〔收錄〕§4）。

---

# 前半：桌遊資料與心得管線

## 6. 執行順序

```
1. Codex 產生 games.json，立倫補繁中名稱
2. 匯入桌遊 → 匯出 → 放進 GAE265G5        import-games → export-games
   （其他組員：下載匯出檔 → 同步          sync-games）
3. Codex 收心得，產生 reviews.json
4. 產生心得摘要、產生心得片段              summarize-reviews、build-excerpts
5. 歸納詞彙表草稿 → 立倫編輯、走 MR → 同步  draft-vocabulary → sync-vocabulary
6. 上標籤 → 立倫刪標籤 → 匯入標籤草稿      draft-tags → import-tags
```

- 第 2 步只做一次：立倫在空的資料庫執行 `import-games`，之後 `games.json` 就不再使用，可以刪掉。其他組員只執行 `sync-games`，否則他們的資料庫會自己給號，編號就對不上。組員拿到新的匯出檔就重跑同步，跑幾次結果都一樣。〔整數編號〕
- 立倫的資料庫要重建時，用 GAE265G5 最新的匯出檔執行 `sync-games`，不重新匯入；`games` 不是空的時候 `import-games` 拒絕執行（§8.1）。〔整數編號〕
- 之後要新增桌遊，到時再另外設計，現在不做。〔整數編號〕
- 部署到 Azure 的正式資料庫也用 `sync-games` 放資料：由立倫把 `DATABASE_URL` 指到正式資料庫後執行。正式資料庫不執行 `import-games`。〔整數編號〕
- 第 3 步之後的指令只有立倫執行；其他組員只需要共用表，不同步推薦用的 4 張表。〔整數編號〕
- 第 4 步不依賴詞彙表，第 2 步之後隨時能跑。〔管線〕總覽
- 補心得之後重跑第 4、6 步。〔管線〕總覽
- 詞彙表只在新增桌遊時考慮重新歸納；補心得、改提示詞都不重新歸納。〔改版〕§2
- 換 embedding 模型：重跑第 4 步。〔改版〕§6
- 子指令名稱〔Q8〕。

## 7. 批次指令的共用規則

### 7.1 怎麼執行

```
uv run python -m app.domains.games_advisor.commands <子指令> <參數>
```

- 模組名稱 `commands` 與子指令名稱〔Q8〕。比照 `app/dev/seed.py` 用 `python -m` 執行，檔案路徑當參數。〔收錄〕§4、〔管線〕§8
- 指令模組的角色和 `router` 相同：只解析參數、建立 provider、呼叫 service、印出結果；service 再呼叫 repository 與 integrations。不放 `app/dev/`。〔管線〕§8

| 子指令 | 做什麼 | 讀 | 寫 | 用 LLM | 用 embedding |
|---|---|---|---|---|---|
| `import-games <games.json> --first-four <4 個 bgg_id>` | 匯入桌遊（§8.1），只有立倫在空資料庫執行一次 | `games.json` | `games`、`game_genres` | — | — |
| `export-games --out <匯出檔>` | 匯出共用桌遊資料（§8.10），只有立倫執行 | `games`、`game_genres`、`games.id` 的計數器 | 匯出檔 | — | — |
| `sync-games <匯出檔>` | 同步共用桌遊資料（§8.11），其他組員執行 | 匯出檔 | `games`、`game_genres`、`games.id` 的計數器 | — | — |
| `summarize-reviews <reviews.json>` | 產生心得摘要（§8.3） | `reviews.json` | `games_advisor_review_summaries` | `generate` | 是 |
| `build-excerpts <reviews.json>` | 產生心得片段（§8.4） | `reviews.json` | `games_advisor_review_excerpts` | — | 是 |
| `draft-vocabulary <reviews.json> --out <草稿> --report <報告>` | 歸納詞彙表草稿（§8.5） | `reviews.json` | 詞彙表草稿、歸納報告 | `generate_json` | — |
| `sync-vocabulary <tag_vocabulary.json>` | 同步詞彙表（§8.6） | 詞彙表檔案 | `games_advisor_tags`；刪代碼時也刪 `games_advisor_game_tags` | — | — |
| `draft-tags <reviews.json> --out <草稿>` | 上標籤（§8.7） | `reviews.json`、`games_advisor_tags` | 標籤草稿 | `generate_json` | — |
| `import-tags <草稿>` | 匯入標籤草稿（§8.8） | 標籤草稿 | `games_advisor_game_tags` | — | — |
| `eval` | 評估題組（§15） | `eval_cases.json` | 評估報告 | `respond`；評審用 `generate_json`（§15.6） | 是 |

- `summarize-reviews`、`build-excerpts`、`draft-tags` 可以加 `--bgg-id <id>`，只跑指定的桌遊，用來補跑失敗的那幾款；可以給多個〔Q8〕。〔管線〕§8

### 7.2 規則

1. **先匯入桌遊。** `reviews.json` 出現資料庫沒有的 `bgg_id` 時，整個指令拒絕執行：什麼都不寫，也不呼叫模型。〔管線〕§8
2. **每款桌遊一個交易，某款失敗不影響其他款。** 重跑就是覆蓋：先刪該款的舊資料再寫入，不記錄進度。〔管線〕§8
   - 匯入桌遊與同步例外：整份檔案一個交易。匯入只在空資料庫執行（§8.1）；同步以 `id` 認出同一款，已存在就直接更新欄位、不先刪再寫（§8.11）。如果先刪再寫，參照這款的類型、心得摘要、標籤與心得片段會跟著被刪。〔收錄〕§4、〔改表〕、〔整數編號〕
3. **需要 LLM 的指令遇到 `LLM_PROVIDER=fake` 就拒絕執行**，印出「需要真的模型，請設定 LLM_*」。範圍是 `draft-vocabulary`、`draft-tags`、`summarize-reviews`，以及 `eval`（§15）。`local` 不擋。pytest 直接把 fake 傳進 service，不經過這個檢查。〔LLM 設定〕§4
4. **批次用的 LLM provider：複製一份 settings、換掉三個值，再交給 factory。** 寫成 `games_advisor` 裡的一個小函式，用單元測試確認三個值都換對。〔LLM 設定〕§2、〔提案 §7〕

   ```python
   batch_settings = settings.model_copy(update={
       "llm_model": settings.llm_batch_model or settings.llm_model,
       "llm_reasoning_effort": None,   # 用模型預設
       "llm_timeout_seconds": 300,
   })
   llm = get_llm_provider(settings.llm_provider, batch_settings)
   ```

5. **embedding provider：** 用 `GAMES_ADVISOR_EMBEDDING_*` 組出 `EmbeddingConfig`，交給 `get_embedding_provider`；每個批次指令各自建一個。〔改版〕§4、〔提案 §7〕
6. **模型出錯時：**〔提案 §5〕

   | 例外 | 批次指令怎麼做 |
   |---|---|
   | `LLMOutputRejected`（內容過濾、拒答、截斷、不是合法 JSON） | 重試 1 次，仍然失敗就跳過這一款 |
   | `LLMUnavailable`（逾時、連線失敗、429、5xx，SDK 已重試 2 次） | 跳過這一款 |
   | `EmbeddingError`、`EmbeddingUnavailable` | 跳過這一款 |
   | 其他 `LLMError`（金鑰錯誤、schema 不符合 strict 規定） | 不攔截，整個指令失敗 |

   跳過的款在指令結束時列出來，附上原因。「重試 1 次再跳過」寫成三個用 LLM 的指令共用的函式，在上標籤的測試裡測（§8.7）。〔Q6〕

7. **結束碼**〔Q8〕：0 全部完成；1 沒有完成（拒絕執行或整個失敗，什麼都沒寫）；2 部分完成（有款被跳過）。
8. **沒有權限問題：** 本機手動執行，沒有登入者。下面每張表的「沒有權限」都是不適用。

共用規則的測試（指令經過 `main()`、連 CI 的 PostgreSQL，比照 `tests/dev/test_seed.py`）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| `LLM_PROVIDER=fake` | 執行 `summarize-reviews`、`draft-vocabulary`、`draft-tags`（各一個案例） | 結束碼 1；印出「需要真的模型，請設定 LLM_*」；資料庫與輸出檔都沒有變 |
| `LLM_PROVIDER=fake` | 執行 `build-excerpts`、`import-games`、`export-games`、`sync-games`、`sync-vocabulary`、`import-tags` | 照常執行，不被這條擋 |
| `reviews.json` 有資料庫沒有的 `bgg_id` | 執行任一讀 `reviews.json` 的指令（service 層，假的 repository） | 結束碼 1；印出是哪個 `bgg_id`；沒有呼叫模型；沒有寫入 |
| `LLM_BATCH_MODEL=b`、`LLM_MODEL=a`、`LLM_REASONING_EFFORT=low`、`LLM_TIMEOUT_SECONDS=30` | 呼叫批次 settings 函式 | `llm_model=b`、`llm_reasoning_effort=None`、`llm_timeout_seconds=300`；原本的 settings 不變 |
| `LLM_BATCH_MODEL` 留空、`LLM_MODEL=a` | 同上 | `llm_model=a` |
| 沒有權限 | — | 不適用：本機指令，沒有登入者 |

## 8. 各指令

### 8.1 匯入桌遊 `import-games`

`games.json` 的格式（〔收錄〕§4：格式寫進 spec，Codex 照格式產生）：

```json
{
  "games": [
    {
      "bgg_id": 900001,
      "name": "範例桌遊甲",
      "english_name": "Example Game A",
      "min_players": 2,
      "max_players": 4,
      "min_playtime": 30,
      "max_playtime": 45,
      "min_age": 10,
      "weight": 1.85,
      "categories": ["Card Game", "Fantasy"],
      "mechanics": ["Hand Management", "Set Collection"],
      "types": ["family"]
    }
  ]
}
```

| 欄位 | BGG XML API 來源〔收錄〕§2 | 檢查 |
|---|---|---|
| `bgg_id` | thing 的 `id` | 正整數，檔案內不重複 |
| `name` | 立倫手填 | 不是空白 |
| `english_name` | `name type="primary"` | 不是空白 |
| `min_players`、`max_players` | `minplayers`、`maxplayers` | 整數，1 ≤ 最少 ≤ 最多 |
| `min_playtime`、`max_playtime` | `minplaytime`、`maxplaytime` | 整數，1 ≤ 最短 ≤ 最長 |
| `min_age` | `minage` | 整數，≥ 0 |
| `weight` | `statistics` 的 `averageweight` | 1 ≤ 難度 ≤ 5 |
| `categories` | `link type="boardgamecategory"` 的 `value` | 字串陣列，可以是空的；元素不是空白、不重複 |
| `mechanics` | `link type="boardgamemechanic"` 的 `value` | 同上 |
| `types` | `statistics` 的 `ranks` 裡 `type="family"` 的大類排名，換成 `genres.code`；Codex 先確認 API 有回這一段，抓不到的由立倫手填〔改表〕 | 字串陣列，可以是空的；元素是 `genres.code`、不重複 |

- 12 個欄位都必填，不接受其他欄位；數值範圍〔Q8〕。`games.json` 沒有桌遊編號，編號由資料庫自動給。〔改表〕、〔整數編號〕
- 人數、時長、年齡一律用 BGG 的數字，不和盒子或代理商頁比對。〔收錄〕§3
- Codex 收心得時也讀這個檔案的 `bgg_id`、`name`、`english_name`（`prompts/collect-reviews.md` 寫「欄位名稱以檔案為準」）。
- 只有立倫在空的資料庫執行一次；之後 `games.json` 不再使用，可以刪掉。其他組員用同步（§8.11）。〔整數編號〕

行為：

1. 先檢查：
   - 整份檔案照上表檢查。
   - `--first-four` 剛好 4 個 `bgg_id`、不重複，而且都在檔案裡。

   有任何一項不符合，就整份拒絕、什麼都不寫，並印出是哪一款（`bgg_id`）的哪個欄位，或 `--first-four` 哪裡不對。〔Q3〕、〔整數編號〕
2. `games` 不是空的：拒絕執行，印出「資料庫已經有桌遊；要重建請用 GAE265G5 最新的匯出檔執行 sync-games」。〔整數編號〕
3. 依序寫入：先寫 `--first-four` 的 4 款，照參數的順序拿到 1–4 號；其他款照檔案順序拿 5 號之後的號碼。`id` 都由資料庫自動給。類型照 `types` 寫進 `game_genres`。〔收錄〕§4、〔改表〕、〔整數編號〕
4. 整份檔案一個交易：任何一步失敗，什麼都不寫。
5. 結束時印出匯入幾款、1–4 號各是哪一款，並提醒「記得執行 export-games，把匯出檔放進 GAE265G5」。〔整數編號〕

立倫實際執行的指令：

```
uv run python -m app.domains.games_advisor.commands import-games <games.json> \
  --first-four 400566,144734,171623,128882
```

測試（指令與 repository 連 CI 的 PostgreSQL〔驗收〕§1；用 5 款自編的假桌遊〔收錄〕§4，`--first-four` 指定其中 4 款、順序和檔案不同）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 空資料庫，檔案有 5 款 | `import-games --first-four` 指定第 5、3、1、4 款 | 結束碼 0；第 5、3、1、4 款依序是 1–4 號，第 2 款是 5 號；欄位和檔案相同；`types` 寫進 `game_genres`；印出匯入 5 款 |
| 資料庫已有桌遊 | 同上 | 結束碼 1；印出要用同步重建；資料庫沒有任何變動 |
| `--first-four` 只給 3 個、給了 5 個，或有重複 | 同上 | 結束碼 1；印出 `--first-four` 哪裡不對；資料庫沒有任何變動 |
| `--first-four` 有一個 `bgg_id` 不在檔案裡 | 同上 | 同上 |
| 匯入後 | 不給 `id` 再寫入一款 | 拿到 6 號 |
| 缺必填欄位（例如沒有 `name`） | 同上 | 結束碼 1；印出 `bgg_id` 與欄位；資料庫沒有任何變動 |
| `name` 是空白 | 同上 | 同上 |
| `min_players` 大於 `max_players` | 同上 | 同上 |
| `weight` 是 5.5 | 同上 | 同上 |
| 兩款的 `bgg_id` 相同 | 同上 | 同上 |
| `types` 有不認得的代碼（例如 `partyy`） | 同上 | 同上 |
| 有不認得的欄位（例如拼錯成 `min_player`，或多帶了 `id`） | 同上 | 同上 |
| `min_playtime` 是 0 | 同上 | 同上 |
| 檔案不存在，或不是合法 JSON | 同上 | 結束碼 1；資料庫沒有任何變動 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.2 `reviews.json`：心得管線的輸入

格式由 Codex 的提示詞定義（[collect-reviews.md](prompts/collect-reviews.md)）。〔心得來源〕§6

後端只讀這些欄位：

| 欄位 | 後端怎麼用 |
|---|---|
| `bgg_id` | 對到 `games.bgg_id` |
| `source_url` | 複製到心得片段；上標籤檢查引用 |
| `site_name` | 複製到心得片段 |
| `language` | 複製到心得片段；切片段時決定用中文字或英文單字計算長度 |
| `text` | 交給 LLM 讀；切成心得片段 |

- `title`、`author`、`published_on`、`retrieved_on`、`shortfalls` 後端不讀。
- 格式檢查：上表 5 個欄位都在；`language` 只有 `zh-TW`、`en`；`text` 不是空白。不符合就整份拒絕。〔Q3〕
- 每款 0–5 篇。`below_minimum`（少於 2 篇，或只來自 1 個網站）照跑；0 篇的桌遊沒有任何輸出。〔管線〕§7、〔心得來源〕§2
- 0 篇的桌遊如果有上一次產生的資料，重跑時清空。作者要求刪除心得時，刪掉 `reviews.json` 裡那篇再重跑就清乾淨。〔Q4〕
  - `summarize-reviews`：刪掉該款的心得摘要。
  - `build-excerpts`：刪掉該款全部心得片段。
  - `draft-tags`：該款放進草稿，`tags` 是空陣列；匯入後標籤清空。
  - 所以沒帶 `--bgg-id` 時，處理的是資料庫裡全部桌遊，不只 `reviews.json` 出現的。

### 8.3 產生心得摘要 `summarize-reviews`

規則〔管線〕§5：

- 每款至少有 1 篇心得的桌遊，呼叫 1 次 `generate`，一次讀完該款全部心得。和上標籤分開呼叫。
- 寫一段 120–200 字的繁中摘要。寫：氣氛、互動方式、對運氣與策略的感受、適合的場合；英文心得也寫成繁中。
- 不寫：整體好壞（好玩、無聊）；價格、版本、翻譯、購買管道；規則說明；心得沒提到的特性。
- 標籤的「不和條件、BGG 欄位重複」不適用：摘要只用來算相似度，寫到「合作」反而有助於比對。
- 摘要轉成向量，和模型名稱一起寫進 `games_advisor_review_summaries` 的同一列，同一個交易。〔改版〕§5、〔改表〕
- 字數不由程式檢查，只寫在提示詞裡〔Q8〕。
- 不依賴詞彙表：可以在審核詞彙表時先跑，詞彙表改版也不用重產。〔管線〕§5

測試（service；假的 repository、`FakeLLMProvider`、`FakeEmbeddingProvider`）。LLM 出錯時的重試與跳過在上標籤測過，這裡不重測；「某款失敗時舊資料保留」用 embedding 拋錯來測，不用改整合層提案。〔Q6〕

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 2 款假桌遊，各有 2 篇心得 | 執行 | 每款呼叫 1 次 `generate`，提示詞含該款全部心得的 `text`；每款寫入摘要、向量、模型名稱 |
| embedding 用 fake | 同上 | `embedding_model` 是 `fake` |
| embedding 設定的模型名稱是 `m1` | 同上 | `embedding_model` 是 `m1` |
| 某款已有舊摘要 | 重跑 | 舊摘要被新摘要取代 |
| `--bgg-id` 指定 1 款 | 執行 | 只呼叫 1 次 `generate`，只寫那一款 |
| 第 1 款已有舊摘要，`embed` 拋 `EmbeddingError` | 執行 | 第 1 款的摘要與向量都不寫，舊摘要保留；第 2 款照寫；列出第 1 款與原因；結束碼 2 |
| 某款 0 篇心得，原本有摘要 | 執行 | 不呼叫 LLM；該款的心得摘要被刪掉 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.4 產生心得片段 `build-excerpts`

規則〔管線〕§6：

1. 每篇心得的 `text` 依 `\n\n` 切成段落。
2. 少於 40 個中文字或 25 個英文單字的段落，併到同一篇的下一段；最後一段併到前一段。
3. 超過 300 個中文字或 150 個英文單字的段落，在句號處切開。
4. 存原文，不翻譯。不用 LLM 切：程式切法可以重現、可以寫測試。
5. 每段從所屬心得複製 `source_url`、`site_name`、`language`。〔心得來源〕§5
6. 每款的片段一起送 `embed`，向量和 `GAMES_ADVISOR_EMBEDDING_MODEL`（fake 記 `fake`）一起寫入。〔改版〕§5
7. 重跑時先刪該款全部舊片段再寫入，片段 ID 會換新。〔管線〕§8

- 不需要 LLM，`LLM_PROVIDER=fake` 也能跑。〔LLM 設定〕§4
- 切法的細節〔Q8〕：
  - 依該篇的 `language` 決定算法：中文算字元數（不含空白），英文算以空白分隔的單字數。
  - 「句號」指中文的「。！？」、英文後面接空白的「. ! ?」。在不超過上限的最後一個句號後面切；整段都沒有句號就照上限切。
  - 整篇只有一段而且太短時，保留成 1 段。

切段函式的測試（純函式，不連資料庫）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 中文心得 3 段，各 50–200 字 | 切段 | 3 段，文字和原段落相同 |
| 中間有一段 20 字 | 同上 | 那一段併到下一段 |
| 最後一段 20 字 | 同上 | 併到前一段 |
| 一段 450 字，中間有句號 | 同上 | 切成每段不超過 300 字，切點在句號後面 |
| 一段 450 字，完全沒有句號 | 同上 | 照 300 字的上限切 |
| 整篇只有一段，20 字 | 同上 | 保留成 1 段 |
| 英文心得有一段 20 個單字 | 同上 | 用單字數判斷，併到下一段 |
| 同一款的兩篇心得 | 同上 | 不跨篇合併 |
| 長度上下限換成其他值 | 同上 | 照新的值切 |

service 的測試（假的 repository、`FakeEmbeddingProvider`）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 2 款假桌遊各有心得 | 執行 | 每款呼叫 1 次 `embed`；片段帶 `source_url`、`site_name`、`language`、向量、模型名稱 |
| 某款已有舊片段 | 重跑 | 舊片段全部刪掉，換成新的 |
| `--bgg-id` 指定 1 款 | 執行 | 只動那一款 |
| 某款 `embed` 拋 `EmbeddingError` | 執行 | 那一款不寫，舊片段保留；其他款照寫；結束碼 2 |
| 某款 0 篇心得，原本有片段 | 執行 | 不呼叫 `embed`；舊片段全部刪掉 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.5 歸納詞彙表草稿 `draft-vocabulary`

步驟〔管線〕§1：

1. **擷取候選詞**：每款至少有 1 篇心得的桌遊，呼叫 1 次 `generate_json`，一次讀完該款全部心得。輸出：

   ```json
   {"candidates": [{"term": "笑聲不斷", "description": "一句描述", "source_urls": ["https://example.com/a"]}]}
   ```

   - `term` 是 2–8 字的繁中短詞。提示詞寫明只描述玩起來的感受，以及〔詞彙表〕§3 列出的 4 類不能變成標籤的內容。
   - 提示詞附上立倫指定的 35 個優先候選詞：心得裡有提到對應的感受時，優先用這些詞；心得沒提到就不收；其他重要的感受照樣可以擷取。〔改表〕

     > 派對、嘴砲、合作、搞笑、滑稽、出糗、幽默、放鬆、懸疑、推理、分析、決策、觀察、掌控、自由、分配、學習、專注、活用、動手、主觀、客觀、聯誼、交心、探索、融合、模擬、組合、拆開、破壞、競爭、刺激、緊張、靜止、平靜

   - 這些詞和〔詞彙表〕§3 衝突的（例如「合作」和 BGG 機制重複、「派對」和類型重複、「主觀／客觀」是同一個面向的兩個方向、「搞笑／滑稽／幽默」是同義詞），不在提示詞裡先刪，由合併同義詞與立倫審核照原本的規則處理。〔改表〕

2. **合併同義詞**：全部候選詞由程式編號（`c1`、`c2`…），交給 LLM 呼叫 1 次。輸出：

   ```json
   {
     "tags": [
       {"code": "laughter", "name": "歡樂爆笑", "definition": "玩的過程常有大笑、吵鬧的場面", "candidate_ids": ["c1", "c7"]}
     ],
     "discarded": [{"candidate_id": "c3", "reason": "和 c5 是同一個面向的反方向"}]
   }
   ```

   - 每個面向只留一個方向，反方向的候選詞捨棄並寫出原因；最多 30 個。
   - 程式依 `candidate_ids` 算出每個標籤出現在幾款，由多到少排序。

3. **寫兩個檔案**：
   - 詞彙表草稿（`--out`）：格式同 `tag_vocabulary.json`（§8.6），只有代碼、名稱、定義。檔案已存在就拒絕，在呼叫 LLM 之前檢查。〔管線〕§1、〔改版〕§2
   - 歸納報告（`--report`，repo 外，Markdown）：每個標籤合併了哪些候選詞、出現在哪幾款、依據的 `source_url`；被捨棄的候選詞與原因；被跳過的桌遊。

4. **立倫審核**：參考報告直接編輯詞彙表檔案，以 MR 提交。可以刪除、合併、改名稱、改寫定義、改代碼；不能新增報告裡找不到依據的標籤。〔管線〕§1

- 這個指令不寫資料庫。
- 草稿不做同步的格式檢查（代碼格式、數量），由同步把關〔Q8〕。
- 重新歸納時寫到另一個路徑，由立倫把要的標籤手動搬進 `tag_vocabulary.json`，走 MR。〔改版〕§2

測試（service；假的 repository、`FakeLLMProvider`）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 3 款各有心得 | 腳本：3 次候選詞＋1 次合併 | `generate_json` 呼叫 4 次；草稿只有 `code`、`name`、`definition`，依出現款數由多到少排序；報告列出合併的候選詞、款、網址、捨棄的候選詞與原因 |
| 草稿路徑已有檔案 | 執行 | 結束碼 1；沒有呼叫 LLM；原檔案內容不變 |
| 某款擷取候選詞拋 `LLMUnavailable` | 執行 | 那一款列進報告的跳過清單；其他款照樣合併；結束碼 2 |
| 合併那次連續 2 次 `LLMOutputRejected` | 執行 | 兩個檔案都不寫；結束碼 1 |
| 某款 0 篇心得 | 執行 | 不為它呼叫 LLM |
| 沒有權限 | — | 不適用：本機指令 |

### 8.6 同步詞彙表 `sync-vocabulary`

`tag_vocabulary.json` 的格式（例子取自〔詞彙表〕§2）：

```json
{"tags": [{"code": "laughter", "name": "歡樂爆笑", "definition": "玩的過程常有大笑、吵鬧的場面"}]}
```

格式檢查，有一項不符合就整份拒絕〔管線〕§1：

- 代碼符合 `^[a-z][a-z0-9_]*$`，而且不重複。
- 名稱、定義都不是空白，名稱不重複。
- 標籤數不超過 30（硬性上限）。

依代碼比對檔案和資料表〔改版〕§1：

| 檔案的變動 | 同步怎麼做 | 印出 |
|---|---|---|
| 刪掉代碼 | 刪掉這個標籤，連帶刪掉所有桌遊上的這個標籤 | 哪幾款少了哪個標籤 |
| 新增代碼 | 新增標籤，還沒有任何桌遊有它 | 提醒：重跑上標籤（全部桌遊）並重做人工驗證 |
| 改代碼 | 當作刪掉舊代碼、新增新代碼 | 上面兩種都印 |
| 只改名稱或定義 | 原地更新，桌遊上的標籤與信心分數都保留 | 哪些標籤改了，可以考慮重標 |

- 程式不強制重標；重標時一律全部桌遊重跑。〔改版〕§1
- 整份同步在一個交易裡完成〔Q8〕。
- 同步之後，下一則玩家訊息的工具 enum 就用新清單，不用重啟後端（§11.1）。〔改版〕§1
- 評估題組用到的代碼都要在詞彙表裡，這個 pytest 寫在評估題組（§15.5）。〔改版〕§3

測試（service 用假的 repository；連帶刪除另在 §9 用 PostgreSQL 測）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 資料表是空的，檔案有 3 個標籤 | `sync-vocabulary` | 3 個標籤 |
| 刪掉 1 個代碼，2 款有這個標籤 | 同上 | 標籤和 2 款上的這個標籤都刪掉；印出這 2 款 |
| 新增 1 個代碼 | 同上 | 新增；沒有桌遊有它；印出重標提醒 |
| 改掉 1 個代碼 | 同上 | 舊代碼與桌遊上的舊標籤刪掉、新代碼新增；兩種訊息都印 |
| 只改 1 個標籤的定義 | 同上 | 原地更新；桌遊上的標籤與信心分數不變；印出「可以考慮重標」 |
| 檔案和資料表相同 | 同上 | 沒有變動，不印提醒 |
| 代碼有大寫字母，或以數字開頭 | 同上 | 整份拒絕，資料表不變；印出是哪個代碼 |
| 代碼重複 | 同上 | 整份拒絕 |
| 名稱重複 | 同上 | 整份拒絕 |
| 名稱或定義是空白 | 同上 | 整份拒絕 |
| 31 個標籤 | 同上 | 整份拒絕 |
| 剛好 30 個標籤 | 同上 | 成功 |
| 同步到一半寫入失敗（連 PostgreSQL） | 同上 | 整份回滾，資料表和同步前相同 |
| 檔案不是合法 JSON，或沒有 `tags` | 同上 | 拒絕 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.7 上標籤 `draft-tags`

1. 每款至少有 1 篇心得的桌遊，呼叫 1 次 `generate_json`，一次讀完該款全部心得（最多 5 篇，不抽樣）。代碼用 strict schema 的 enum，值從 `games_advisor_tags` 讀。〔管線〕§2、〔詞彙表〕§1 輸出：

   ```json
   {"tags": [{"code": "laughter", "confidence": 0.8, "source_urls": ["https://example.com/a", "https://example.com/b"]}]}
   ```

2. 給分標準寫在提示詞裡〔管線〕§2：

   | 分數 | 標準 |
   |---|---|
   | 0.8–1.0 | 2 篇以上心得明確提到 |
   | 0.5–0.7 | 1 篇明確提到，或 2 篇以上間接提到 |
   | 0.2–0.4 | 只有 1 篇間接提到 |
   | 不輸出 | 沒有心得提到 |

   - 明確提到：直接描述這種感受，例如「大家笑到不行」。間接提到：要推論才看得出來，例如「很適合聚會」對應歡樂爆笑。
   - 有心得明確說出相反的感受時，分數降一級。

3. 自動檢查，逐款〔管線〕§3：
   1. 代碼都在詞彙表裡、分數在 0–1、同一款沒有重複的標籤。
   2. 每個標籤至少引用 1 篇心得，引用的都是這一款的心得（`source_url` 屬於 `reviews.json` 裡這一款）。
   3. 分數和引用篇數一致：0.8 以上至少引用 2 篇。

   不通過就重試 1 次；仍不通過就跳過這一款，列在結束時的輸出。

4. 提醒，不算失敗〔管線〕§3：每個標籤被幾款使用；沒有任何一款使用、或「16 款中有 13 款以上」使用的標籤，標為「詞彙表可能有問題」（門檻寫成已匯入桌遊數的 80% 以上，16 款時就是 13 款〔Q8〕）；沒有任何標籤的桌遊。
5. 寫標籤草稿（repo 外）：

   ```json
   {
     "games": [
       {
         "bgg_id": 900001,
         "name": "範例桌遊甲",
         "tags": [
           {"code": "laughter", "confidence": 0.8, "source_urls": ["https://example.com/a", "https://example.com/b"]}
         ]
       }
     ]
   }
   ```

   - 被跳過的款不放進草稿，所以匯入時不會動它的標籤。
   - LLM 判斷沒有任何標籤的款，照樣放進草稿，`tags` 是空陣列；匯入後該款沒有標籤。
   - 每次都是全新草稿，不記得上次刪了哪些，人工驗證要重做。〔管線〕§4
   - 同時寫一份原始檔（檔名是草稿檔名加 `.original`，例如 `tags-draft.original.json`），立倫不要編輯它。匯入時拿草稿和原始檔比，確認「只有刪除」。〔Q5〕
   - 0 篇心得的桌遊也放進草稿，`tags` 是空陣列。〔Q4〕
   - 草稿路徑已存在就拒絕；詞彙表是空的（還沒同步）就拒絕〔Q8〕。
   - 跳過清單與提醒印在終端機，不另寫報告檔〔Q8〕。

測試（service；假的 repository、`FakeLLMProvider`）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 2 款，詞彙表 4 個標籤 | 腳本：2 次合格輸出 | 草稿有 2 款，每個標籤有代碼、分數、網址；原始檔和草稿內容相同；schema 的 enum 等於資料表的 4 個代碼；`games_advisor_game_tags` 沒有變 |
| 第 1 次輸出有詞彙表沒有的代碼，第 2 次合格 | 執行 | 重試 1 次後寫進草稿 |
| 第 1 次 `LLMOutputRejected`，第 2 次合格 | 執行 | 重試 1 次後寫進草稿 |
| 連續 2 次 `LLMOutputRejected` | 執行 | 那一款跳過；列出原因；結束碼 2 |
| 兩次都不合格：分數 1.2 | 執行 | 那一款跳過、不在草稿；列出原因；其他款照寫；結束碼 2 |
| 兩次都不合格：同一款重複標籤 | 執行 | 同上 |
| 兩次都不合格：標籤沒有引用心得 | 執行 | 同上 |
| 兩次都不合格：引用別款的心得網址 | 執行 | 同上 |
| 兩次都不合格：0.8 只引用 1 篇 | 執行 | 同上 |
| `generate_json` 拋 `LLMUnavailable` | 執行 | 那一款跳過 |
| 某個標籤沒有任何一款使用 | 執行 | 提醒「詞彙表可能有問題」 |
| 某個標籤用在 80% 以上的桌遊 | 執行 | 同上 |
| 某款 LLM 回空的 `tags` | 執行 | 草稿有該款、`tags` 是空的；提醒「沒有任何標籤」 |
| `--bgg-id` 指定 1 款 | 執行 | 草稿只有那一款 |
| 草稿路徑已有檔案 | 執行 | 結束碼 1；沒有呼叫 LLM；原檔案內容不變 |
| 詞彙表是空的（還沒同步） | 執行 | 結束碼 1；沒有呼叫 LLM；提示先同步詞彙表 |
| 某款 0 篇心得 | 執行 | 不為它呼叫 LLM；草稿有該款、`tags` 是空的 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.8 匯入標籤草稿 `import-tags`

1. 先檢查整份草稿，有一項不符合就整份拒絕〔管線〕§4、〔改版〕§1：
   - 草稿的代碼都在詞彙表裡。產生草稿之後又同步過詞彙表時會不符合，提示重跑上標籤。
   - 和原始檔比，只有刪除：沒有多出標籤、分數沒有改。原始檔不見就拒絕。〔Q5〕
   - `bgg_id` 都在資料庫裡。
2. 每款一個交易：刪掉該款的舊標籤，寫入草稿裡的標籤，包括低於 0.5 的。〔管線〕§2、§4
3. 只替換草稿裡有的桌遊，其他款不動。〔管線〕§4
4. `source_urls` 不存。〔管線〕§4

測試（service；假的 repository）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 草稿沒有修改 | `import-tags` | 桌遊的標籤和草稿相同，0.3 的標籤也在 |
| 刪掉 1 個標籤 | 同上 | 那一款少了那個標籤 |
| 刪掉某款的整個項目 | 同上 | 那一款的標籤不變 |
| 草稿只有 1 款（用 `--bgg-id` 產生） | 同上 | 其他款的標籤不變 |
| 某款原本就有標籤 | 同上 | 換成草稿裡的 |
| 多出一個標籤 | 同上 | 整份拒絕；資料庫不變 |
| 改了分數 | 同上 | 整份拒絕；資料庫不變 |
| 代碼在產生草稿後被同步刪掉 | 同上 | 整份拒絕；提示重跑上標籤 |
| 原始檔不見 | 同上 | 整份拒絕；資料庫不變 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.9 向量的共用規則

- 兩種向量：心得摘要向量用來排序，心得片段向量用來找推薦理由的出處。〔比對〕§4、§6
- provider、模型名稱、維度都讀 `GAMES_ADVISOR_EMBEDDING_*`（§4.1）。〔改版〕§4
- 每個向量記下產生它的模型；用 fake 時記 `fake`。記的是部署名稱，部署名稱和模型名稱相同；之後換到別的 Foundry，只要沿用這個命名就不用重產。〔改版〕§5、〔部署〕§5
- 換模型：重跑 `summarize-reviews`、`build-excerpts`。心得摘要會跟著重寫；不另寫「只重算向量」的指令。〔改版〕§6
- 改維度：新增一個 migration，清空兩種向量（心得片段整列刪掉）、改欄位維度，再重跑上面兩個指令。現在不寫。〔改版〕§6
- 重產期間不用特別處理：「查桌遊」把模型和目前設定不同的向量當作沒有向量。「查桌遊」的這條過濾與 warning log、評估題組開始前的檢查，寫在 §11.6、§15.1。〔改版〕§5、§6

### 8.10 匯出共用桌遊資料 `export-games`

立倫匯入之後執行，把共用表匯出成檔案，讓其他組員同步。〔整數編號〕

匯出檔的格式（放在團隊共用雲端資料夾 GAE265G5，只放最新的一份、每次覆蓋；不進 repo）：

```json
{
  "next_id": 4,
  "games": [
    {
      "id": 1,
      "bgg_id": 900001,
      "name": "範例桌遊甲",
      "english_name": "Example Game A",
      "min_players": 2,
      "max_players": 4,
      "min_playtime": 30,
      "max_playtime": 45,
      "min_age": 10,
      "weight": 1.85,
      "categories": ["Card Game", "Fantasy"],
      "mechanics": ["Hand Management", "Set Collection"],
      "types": ["family"]
    }
  ]
}
```

- `games` 的每一款是 `games.json` 的 12 個欄位加上 `id`，照 `id` 由小到大排。
- `next_id`：資料庫計數器的下一個號碼。刪掉編號最大的桌遊之後，`next_id` 不會跟著變小。例如 3 款刪掉第 3 款，`next_id` 仍然是 4。

行為：

1. 讀 `games`、`game_genres` 與 `games.id` 的計數器，寫成匯出檔。只讀資料庫，不改任何資料。
2. `games` 是空的：拒絕，結束碼 1，不產生檔案。
3. `--out` 指定的檔案已經存在：直接覆蓋。
4. 結束時印出匯出幾款、`next_id`，並提醒「把匯出檔放進 GAE265G5，覆蓋舊的那份」。

測試（連 CI 的 PostgreSQL；假桌遊）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 資料庫有 3 款 | `export-games --out <檔案>` | 結束碼 0；檔案有 3 款，`id`、欄位、`types` 和資料庫相同；`next_id` 是 4 |
| 3 款刪掉第 3 款 | 同上 | 檔案有 2 款；`next_id` 仍然是 4 |
| 空資料庫 | 同上 | 結束碼 1；沒有產生檔案 |
| 沒有權限 | — | 不適用：本機指令 |

### 8.11 同步共用桌遊資料 `sync-games`

其他組員拿到新的匯出檔後執行；立倫重建資料庫時也用（§6）。同步後，資料庫的共用表和匯出檔完全一樣。〔整數編號〕

行為：

1. 先檢查整份匯出檔：`next_id` 是正整數，而且大於所有 `id`；每款的 `id` 是正整數、不重複；其他 12 個欄位照 §8.1 的檢查。有任何一款不符合，就整份拒絕、什麼都不寫，並印出是哪一款（`id`）的哪個欄位。
2. 以 `id` 判斷同一款：
   - 資料庫有同一個 `id`、`bgg_id` 也相同：更新欄位。
   - 資料庫有同一個 `id`，但 `bgg_id` 不同：當成不同的桌遊，先刪掉舊的再照匯出檔寫入。
   - 資料庫沒有這個 `id`：照匯出檔的 `id` 寫入。

   類型照 `types` 整組替換。
3. 匯出檔裡沒有的桌遊從資料庫刪掉，連帶刪除的資料照 §3。組員自己在本機加的桌遊也會被刪；測試請用寫在測試程式裡的假資料（AGENTS.md §2.2）。其他 domain 的資料還參照要刪的桌遊時，資料庫會擋下刪除：整份拒絕、什麼都不寫，印出是哪一款、被哪張表參照，由立倫決定怎麼處理（〔ADR 0003〕）。
4. 把 `games.id` 的計數器設成 `next_id`：之後在這個資料庫新增桌遊，從 `next_id` 開始給號，不會重用以前給過的號碼。
5. 整份檔案一個交易：任何一步失敗，什麼都不寫。
6. 結束時印出新增幾款、更新幾款、刪除幾款，以及 `next_id`。

測試（連 CI 的 PostgreSQL；假桌遊）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 空資料庫，匯出檔有 3 款、`next_id` 4 | `sync-games <匯出檔>` | 結束碼 0；3 列，`id` 與欄位和匯出檔相同；`types` 寫進 `game_genres`；印出新增 3、更新 0、刪除 0 |
| 同步完上一列 | 不給 `id` 寫入一款桌遊 | 拿到 4 號 |
| 空資料庫，匯出檔有 2 款（`id` 1、2）、`next_id` 4 | 同步，再不給 `id` 寫入一款 | 拿到 4 號，不是 3 號 |
| 同一個匯出檔再同步一次 | `sync-games <匯出檔>` | 仍然 3 列；印出新增 0、更新 3、刪除 0 |
| 資料庫有匯出檔沒有的桌遊（例如組員自己加的） | 同上 | 那一款被刪掉；印出刪除 1 |
| 資料庫的 `id` 2 是另一個 `bgg_id` | 同上 | `id` 2 換成匯出檔的那一款 |
| 匯出檔把某款的 `types` 從 `[party, family]` 改成 `[party]` | 同上 | 該款只剩 `party` |
| 立倫的資料庫匯出，再同步到另一個空資料庫 | `export-games` → `sync-games` | 兩個資料庫的 `games`、`game_genres` 完全相同；之後各自新增的下一款都是同一個號碼 |
| 測試裡建一張參照 `games.id` 的假表（不連帶刪除），參照匯出檔沒有的那一款 | `sync-games <匯出檔>` | 結束碼 1；印出那一款與那張表的名稱；資料庫沒有任何變動 |
| 缺 `next_id`，或 `next_id` 不大於最大的 `id` | 同上 | 結束碼 1；印出原因；資料庫沒有任何變動 |
| 兩款的 `id` 相同，或 `id` 是 0、`"a"` | 同上 | 同上 |
| 某款的欄位不符合 §8.1 的檢查（例如 `weight` 是 5.5） | 同上 | 同上 |
| 檔案不存在，或不是合法 JSON | 同上 | 結束碼 1；資料庫沒有任何變動 |
| 沒有權限 | — | 不適用：本機指令 |

## 9. repository 的測試（連 CI 的 PostgreSQL）

〔驗收〕§1：repository 連 CI 內建的 PostgreSQL 測試，比照現有的 seed 測試，資料用自編的假桌遊。「查桌遊」用到的 SQL 篩選與 pgvector 查詢寫在 §11.8。

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 資料表是空的 | 不給 `id` 寫入 3 款桌遊 | 3 列，`id` 自動給 1–3 |
| `id` 已存在 | 用同一個 `id` 寫入新的欄位值 | 欄位更新，心得摘要不變 |
| 有 3 款 | 刪除不在清單裡的桌遊（清單有 `id` 1、2） | 第 3 款刪掉，它的心得摘要等資料一起刪；回傳刪除的款數 |
| 資料表是空的 | 照給的 `id`（1、2）寫入，再把計數器設成 4 | 再不給 `id` 寫入一款，拿到 4 號 |
| 有 3 款，刪掉第 3 款 | 讀計數器的下一個號碼 | 回傳 4 |
| 某款有 2 個類型 | 替換成 1 個 | 該款只剩 1 列；其他款不變 |
| 某款桌遊 | 寫入心得摘要、向量、模型名稱 | `games_advisor_review_summaries` 有 1 列；向量長度等於設定的維度 |
| 某款已有心得摘要 | 再寫一次 | 取代舊的，仍然 1 列 |
| 向量長度和欄位維度不同 | 寫入 | 資料庫拒絕，交易回滾 |
| 某款已有心得片段 | 替換該款的心得片段 | 舊的刪掉、新的寫入；其他款不變 |
| 2 款有某個標籤 | 刪除這個標籤 | 這 2 款上的這個標籤一起刪掉；回傳受影響的桌遊 |
| 某款已有標籤 | 替換該款的標籤 | 舊的刪掉、新的寫入；其他款不變 |
| 同一款同一個標籤 | 寫入兩次 | 違反唯一限制 |
| 詞彙表有 4 個標籤 | 讀全部代碼 | 回傳 4 個代碼 |
| 一組 `bgg_id`，其中一個不存在 | 用 `bgg_id` 查桌遊 | 只回傳存在的；service 據此拒絕執行 |

---

# 後半：推薦對話與 API

資料表（§3）、設定欄位（§4）、程式常數（§4.2）沿用上面的總覽，不重寫。

## 10. 一則訊息怎麼處理

```
玩家送出訊息
  → router：檢查欄位、取得目前使用者，呼叫 service
  → service：
     1. require_role(user, "player", "shop_staff", "admin")
     2. 從資料庫讀 enum，組出「查桌遊」工具定義（§11.1）
     3. 第 1 次 respond(input=玩家訊息, previous_response_id=請求帶來的 id)
          → 要求查詢：執行「查桌遊」（§11），把結果送回
     4. 第 2 次 respond(input=[工具結果], previous_response_id=第 1 次的 id)
          → 要求查詢：再執行一次（通常是放寬條件），把結果送回
     5. 第 3 次 respond(input=[工具結果], previous_response_id=第 2 次的 id,
                       allow_tool_calls=False)
     6. 拿到最終輸出：程式檢查（§12.4），組出卡片與放寬的條件
  → router：回 201
```

- 哪一次 respond 拿到最終輸出就停在那一次，不一定用滿 3 次。迴圈寫在 service，整合層一次只呼叫 1 次模型。〔提案 §3.3〕
- 一則訊息最多呼叫 LLM 3 次；embedding 最多 2 次（查詢帶 `preference_text` 時每次 1 次）。〔ADR 0002〕、〔比對〕§4
- 後端不存對話，聊天時也不寫資料庫。條件與偏好每次都完整放在工具參數裡。〔ADR 0001〕、〔流程〕
- 每次 respond 都重送對話規則（`instructions`）與工具定義，因為 Responses API 不會沿用上一次的 instructions。〔提案 §3.3〕
- 對話用 `LLM_MODEL`、`LLM_REASONING_EFFORT`、`LLM_TIMEOUT_SECONDS`（§4.1，立倫用 `gpt-5.6-luna`、`low`、30 秒）；provider 在後端啟動時建立（既有的 `app.state.llm`）。embedding provider 也在啟動時用 `GAMES_ADVISOR_EMBEDDING_*` 建一個。〔部署〕§1、§4、§6、〔改版〕§4

## 11. 「查桌遊」工具

### 11.1 工具定義

名稱 `search_games`〔Q14〕。參數〔比對〕§8：

| 參數 | 必填 | 型別 | enum 從哪裡來 |
|---|---|---|---|
| `players` | 是 | 整數 1–30 | — |
| `max_minutes`、`min_minutes` | 否 | 整數（分鐘） | — |
| `youngest_age` | 否 | 整數（最年輕玩家的年齡） | — |
| `prefer_tags`、`avoid_tags` | 否 | 字串陣列 | `games_advisor_tags.code` |
| `prefer_categories`、`avoid_categories` | 否 | 字串陣列 | 所有桌遊 `categories` 的聯集 |
| `prefer_mechanics`、`avoid_mechanics` | 否 | 字串陣列 | 所有桌遊 `mechanics` 的聯集 |
| `weight_min`、`weight_max` | 否 | 數字 1–5，可只填一個 | — |
| `preference_text` | 否 | 繁中字串 | — |
| `exclude_game_ids` | 否 | 整數陣列 | 所有桌遊的 `id`〔整數編號〕 |

- 工具是 strict：所有參數都列為 required，選填的寫成可為 null，LLM 沒帶就給 null。〔提案 §3.1〕
- enum 每則玩家訊息都從資料庫讀一次。同步詞彙表或同步桌遊之後，下一則訊息就用新清單，不用重啟後端。〔改版〕§1
- 標籤的繁中名稱與定義寫在 `prefer_tags`、`avoid_tags` 的參數說明裡（每個代碼一行「代碼：名稱——定義」），也是每則訊息從資料庫產生。LLM 靠它把「想要歡樂一點」對到 `laughter`。〔Q13〕
- 某份清單是空的（例如還沒同步詞彙表），工具定義就拿掉對應的參數，不送出空的 enum。〔Q14〕

### 11.2 參數檢查

Azure 的 strict 模式保證型別與 enum，但 `FakeLLMProvider` 不檢查 schema（提案 §6.1），所以 service 自己再檢查一次，pytest 才測得到。

1. 人數超出 1–30：不查詢，把錯誤回給 LLM，讓它向玩家確認。〔流程〕護欄 1、〔比對〕§1
2. 其他參數不合理：比照人數，錯誤回給 LLM。包括時長小於 1、年齡小於 0、難度不在 1–5、下限大於上限（`min_minutes > max_minutes`、`weight_min > weight_max`）、值不在 enum 裡。〔Q12〕
3. 回錯誤也算一次工具呼叫（護欄 3 算的是呼叫次數）。〔Q12〕
4. `preference_text` 是空字串或只有空白時，當作沒帶。`embed` 遇到空白會拋 `ValueError`（提案 §4）。〔Q14〕

錯誤的工具結果：

```json
{"error": "人數要在 1 到 30 之間，請向玩家確認人數。"}
```

### 11.3 篩條件（repository，SQL）

| 條件 | 參數 | 符合的桌遊 | 出處 |
|---|---|---|---|
| 人數 | `players` | `min_players ≤ players ≤ max_players` | 〔比對〕§1 |
| 時長上限 | `max_minutes` | `max_playtime ≤ max_minutes` | 同上 |
| 時長下限 | `min_minutes` | `max_playtime ≥ min_minutes` | 同上 |
| 年齡 | `youngest_age` | `min_age ≤ youngest_age` | 同上 |
| 排除清單 | `exclude_game_ids` | `id` 不在清單裡 | 同上 |

- 時長上下限都和最長時長比：「90 分鐘內」代表最長的一局也在 90 分鐘內，所以 60–120 分鐘的桌遊不符合。〔比對〕§1
- 沒帶的條件不篩。〔流程〕§1
- repository 回傳每款候選桌遊的：基本資料、所有標籤與信心分數（低於門檻的也回，由 service 套門檻）、類別、機制、心得摘要向量的模型名稱，以及相似度（§11.4 第 3 點）。

### 11.4 排序（service）

〔比對〕§2–§5：

1. **結構化分數** = 命中的 `prefer_tags` 的信心分數總和 ＋ 命中的類別數 ＋ 命中的機制數 ＋（難度在範圍內時）1。信心分數低於門檻 0.5 的標籤，當作這款沒有這個標籤。
2. **負面分數**：`avoid_tags`、`avoid_categories`、`avoid_mechanics` 用同樣的算法；難度沒有負面參數。門檻一樣是 0.5。
3. **相似度**：`preference_text` 的向量和心得摘要向量的 cosine 相似度，由 repository 用 pgvector 算（「[RAG 教材有哪些可以重用](issues/01-rag-materials-reuse.md)」的骨架：SQL 篩選後用 pgvector 排序）。沒有心得摘要向量，或向量的模型和目前的 `GAMES_ADVISOR_EMBEDDING_MODEL` 不同，當作沒有向量（§11.6）。
4. **排序**依序比較：
   1. 負面分數，低的在前。
   2. RRF 合併分數，高的在前：結構化分數、相似度各排一次名次，合併分數 = Σ 1/(60 + 名次)。
   3. 難度，低的在前。
   4. 繁中名稱。
5. 取前 3 款。

- 沒帶 `preference_text`：只用結構化名次，不呼叫 `embed`。沒有正面結構化偏好（`prefer_*`、`weight_*` 都沒帶）：只用相似度名次。兩者都沒有（玩家說「都可以」）：直接比難度、名稱，所以會得到最輕鬆的 3 款。〔比對〕§5
- 相似度只用來排序，不設門檻排除桌遊。〔比對〕§4
- 細節〔Q14〕：
  - 同分給同一個名次，下一個名次跳過（1、2、2、4）。沒有向量的桌遊在相似度名次並列最後。
  - 難度範圍含邊界：`weight_min ≤ weight ≤ weight_max`。
  - 繁中名稱依 Unicode 碼位排序。

### 11.5 心得片段（repository，pgvector）

- 前 3 款各從自己的心得片段中取最相近的 2 段（程式常數），每段帶 `id`、`text`、`language`。〔比對〕§6、〔理由〕§4
- 查詢向量：有 `preference_text` 就用它的向量（和排序共用，不重算）；沒有就用該款的心得摘要向量。〔比對〕§6
- 只比模型和目前設定相同的片段。沒有片段，或片段的模型都不同，回空清單。〔比對〕§6、〔改版〕§5
- 沒帶 `preference_text`，而該款的心得摘要向量不能用（沒有或模型不同）時，回空清單。〔Q14〕
- 繁中查詢找英文片段，靠 embedding 模型的跨語言能力，由評估題組檢查。〔比對〕§6

### 11.6 向量的模型不同

- 「查桌遊」遇到模型和目前設定不同的向量，當作沒有向量：心得摘要在相似度名次排最後，心得片段回空清單。整則訊息不失敗。〔改版〕§5
- 同時寫一筆 warning log，寫出是哪幾款、哪一種向量。〔改版〕§5
- 重產向量的期間不用特別處理，也不會拿新舊模型的向量混著比。〔改版〕§6

### 11.7 回傳給 LLM 的內容

```json
{
  "games": [
    {
      "id": 1,
      "name": "範例桌遊甲",
      "min_players": 2, "max_players": 4,
      "min_playtime": 30, "max_playtime": 45,
      "min_age": 10, "weight": 1.85,
      "matched_preferences": {
        "tags": [{"name": "歡樂爆笑", "definition": "玩的過程常有大笑、吵鬧的場面"}],
        "categories": ["Card Game"],
        "mechanics": [],
        "weight_in_range": true
      },
      "matched_avoids": {"tags": [], "categories": [], "mechanics": []},
      "excerpts": [{"id": "<uuid>", "text": "……", "language": "zh-TW"}]
    }
  ]
}
```

- 內容〔理由〕§4：基本資料（也用來回答離題規則的「已推薦桌遊的基本資料」）、命中的偏好、命中的負面偏好、心得片段。欄位名稱〔Q14〕。
- `weight_in_range`：沒帶難度偏好時是 null。
- 不回傳：`title`、`site_name`、`source_url`（LLM 用不到，也避免它在推薦理由裡寫網址）、心得摘要（LLM 寫的，沒有出處）、信心分數。〔理由〕§1、§4
- 0 款時回 `{"games": []}`。

### 11.8 測試

repository（連 CI 的 PostgreSQL，自編的假桌遊〔驗收〕§1）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 3 款：2–4 人、3–5 人、5–8 人 | 查 `players=4` | 回前 2 款；邊界（剛好最少、剛好最多）都算符合 |
| 最長時長 45、60、120 | 查 `max_minutes=60` | 回 45、60 那兩款 |
| 同上 | 查 `min_minutes=60` | 回 60、120 那兩款 |
| 最低年齡 8、10、14 | 查 `youngest_age=10` | 回 8、10 那兩款 |
| 3 款都符合 | 帶 `exclude_game_ids`=[第 1 款] | 只回另外 2 款 |
| 只帶人數 | 查 | 時長、年齡都不篩 |
| 某款有 0.3 和 0.8 的標籤 | 查 | 兩個標籤和信心分數都回傳 |
| 心得摘要向量的模型是目前設定 | 查，帶查詢向量 | 相似度有值，等於 cosine 相似度 |
| 某款的模型不同、某款沒有向量 | 同上 | 這兩款的相似度是空的；回傳模型名稱 |
| 某款有 4 段片段 | 取 2 段，帶查詢向量 | 回最相近的 2 段，由近到遠；只回這一款的 |
| 某款只有 1 段 | 同上 | 回 1 段 |
| 某款的片段模型都不同 | 同上 | 回空清單 |
| 3 款的類別有重複 | 讀類別清單 | 聯集、不重複；機制同理 |
| 詞彙表 4 個標籤 | 讀代碼、名稱、定義 | 4 筆 |
| 3 款 | 讀全部 `id` | 3 個 |

service（假的 repository、`FakeEmbeddingProvider`，不連資料庫〔驗收〕§1）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| A 有 `laughter` 0.9、B 有 0.6 | 查，`prefer_tags=[laughter]` | A 在 B 前面 |
| A 的 `laughter` 是 0.4 | 同上 | A 當作沒有這個標籤，不加分 |
| A 命中 3 個正面偏好和 1 個負面，B 只命中 1 個正面 | 查 | B 在 A 前面（負面優先排後面） |
| A、B 都命中負面，A 的負面分數較低 | 查 | A 在 B 前面 |
| A 的 `avoid_tags` 標籤是 0.4 | 查 | A 不算命中負面 |
| A 結構化第 1、相似度第 3；B 結構化第 2、相似度第 1 | 查 | 照 Σ 1/(60 + 名次) 排：B（1/62＋1/61）在 A（1/61＋1/63）前面 |
| 沒帶 `preference_text` | 查 | 不呼叫 `embed`；只用結構化名次 |
| 只帶 `preference_text` | 查 | 呼叫 1 次 `embed`；只用相似度名次 |
| 只帶人數，難度 2.5、1.5、1.5 | 查 | 1.5 的兩款在前，兩款依繁中名稱排 |
| 兩款結構化分數相同 | 查 | 名次相同，下一款的名次跳過〔Q14〕 |
| 某款沒有向量 | 只帶 `preference_text` | 那一款在相似度名次排最後 |
| 難度剛好等於 `weight_max` | 查，帶 `weight_max` | 算在範圍內〔Q14〕 |
| 5 款都符合 | 查 | 只回 3 款 |
| 帶 `preference_text` | 查 | 心得片段用 `preference_text` 的向量查 |
| 沒帶 `preference_text` | 查 | 心得片段用該款的心得摘要向量查 |
| 某款心得摘要向量的模型不同 | 查 | 當作沒有向量；有 warning log |
| `players` 是 0、31 | 查 | 不呼叫 repository 的查詢；回錯誤 |
| `weight_min` 大於 `weight_max`、`max_minutes` 是 0、代碼不在 enum | 查 | 同上〔Q12〕 |
| `preference_text` 只有空白 | 查 | 當作沒帶，不呼叫 `embed`〔Q14〕 |
| `embed` 拋 `EmbeddingUnavailable` | 查 | 例外往上拋（整則訊息 503，§13.2） |
| 回傳內容 | 查 | 有基本資料、命中的偏好與負面偏好、片段的 `id`、`text`、`language`；沒有網址、心得摘要、信心分數 |
| 組工具定義 | 假 repository 有 4 個代碼、5 個類別 | enum 等於這些值；標籤說明有名稱與定義 |
| 詞彙表是空的 | 組工具定義 | 沒有 `prefer_tags`、`avoid_tags`〔Q14〕 |
| 第 1 則訊息之後，假 repository 的代碼改了 | 第 2 則訊息組工具定義 | enum 是新的代碼 |
| 沒有權限 | — | 不適用：工具只在 service 內部呼叫；權限在 §13.3 測 |

## 12. 對話 service

### 12.1 對話規則（`instructions`）

對話規則是程式裡的一段固定文字，每次 respond 都送（§10）。內容：

| 項目 | 規則 | 出處 |
|---|---|---|
| 條件與偏好 | 依欄位歸類，不看語氣：人數、時長、年齡一律是條件，其他特性是偏好。只有人數是必要條件；沒提時長、年齡就不篩，也不追問。負面偏好只排後面，不排除 | 〔流程〕§1 |
| 追問 | 只講人數、沒提偏好時，追問一次偏好，給 2–3 個選項；玩家回「都可以」就推薦。缺的項目一次問完。最多追問 2 輪，之後有人數就推薦；沒有人數就繼續追問，只問人數 | 〔流程〕§2 |
| 填工具參數 | `preference_text` 把所有正面偏好（包括已轉成 enum 的）寫成一句繁中；玩家沒有偏好時不帶。口語換算難度的參考值，例如「不要太燒腦」是 `weight_max: 2.5`。「工人放置」這類說法由 LLM 轉成 BGG 英文名稱 | 〔比對〕§2、§4 |
| 推薦 | 照工具回傳的順序推薦，不自己挑；最多 3 款 | 〔流程〕§3、〔比對〕總覽 |
| 查無結果 | 放寬一項條件再查：先放寬時長，再放寬年齡，最多一項；還是 0 款就告訴玩家沒有符合的，問要怎麼調整。人數不放寬：只有人數造成查無結果時，建議分桌，問每桌幾個人 | 〔流程〕§4 |
| 推薦後調整 | 加了偏好：帶新偏好重查，已推薦過的桌遊放進 `exclude_game_ids`。改了條件：用新條件重查 | 〔流程〕§5 |
| 離題 | 問已推薦桌遊的基本資料：用工具回傳過的資料回答，沒有就說不知道。問規則或玩法：不解釋，請玩家改用規則問答。無關的話題：簡短拒絕，帶回推薦 | 〔流程〕§6 |
| 語言 | 一律用繁中（台灣用語）回覆；玩家用英文也用繁中回答；BGG 的英文類別與機制名稱翻成中文 | 〔流程〕§3 |
| 推薦理由 | 最多 2 句。寫命中的偏好（標籤用繁中名稱，類別與機制翻成中文）、心得片段印證的感受；命中負面偏好一定要說。不寫條件、信心分數、「幾篇心得提到」、心得片段沒提到的特性。沒有命中的偏好時，寫心得片段裡最突出的感受 | 〔理由〕§1 |
| 引用片段 | 每款的 `excerpt_ids` 最多 2 個；該款有片段時至少引用 1 段；不在句子裡標 [1]、[2] | 〔理由〕§2 |
| `reply` | 不列出桌遊名單（名單只在卡片）；放寬條件時要說放寬了哪一項，例如「沒有 15 分鐘內能玩完的，以下是時長稍長的」 | 〔理由〕§5、〔流程〕§4 |

- 這些行為 pytest 驗不到，由評估題組用真的模型檢查（§15）。〔ADR 0002〕、〔驗收〕§7
- 難度換算的參考值寫對話規則時再訂，由評估題組檢查。
- MR 改到對話規則、工具定義、模型部署、標籤詞彙表或排序用的常數時，跑一次評估題組，把分數貼進 MR。〔驗收〕§3

### 12.2 三道護欄

〔流程〕、〔ADR 0002〕：

1. **人數必填**：`players` 是工具參數唯一的必填欄位；不合理就回錯誤給 LLM（§11.2）。
2. **只推薦工具回傳的桌遊**：最終輸出由程式檢查（§12.4）。
3. **每則訊息最多呼叫 2 次工具**：查過 2 次之後，第 3 次 respond 帶 `allow_tool_calls=False`（雲端實作會送 `tool_choice: "none"`）。〔提案 §3.3〕

模型不照約定回應時，當作拒答（`LLMOutputRejected`），回固定文字 A（§12.6）並記 log。〔Q11〕包括：

- 第 3 次 respond 仍然要求查詢。
- 要求的工具不是 `search_games`。
- 一次要求查詢兩次以上（雲端實作帶 `parallel_tool_calls: false`，只有 fake 做得到）。

### 12.3 最終回覆的格式

LLM 的最終輸出用 strict JSON schema（名稱 `advisor_reply`〔Q14〕）〔理由〕§5：

```json
{
  "reply": "幫你找到 3 款適合 4 個人、輕鬆聊天的桌遊。",
  "recommendations": [
    {"game_id": 1, "reason": "……", "excerpt_ids": ["<uuid>"]}
  ]
}
```

- `recommendations` 最多 3 筆；追問、離題時是空陣列。`excerpt_ids` 最多 2 個。〔理由〕§2、§5
- 最終輸出要和工具在同一個請求裡（`text.format` 加 `tools`）。在 Azure 實際驗證交給第一張實作 ticket；不成立時改用「交卷」工具 `submit_recommendations`，只改 `respond` 的 `output_schema` 一處。〔提案 §10〕

### 12.4 程式檢查

後端不存對話，service 只看得到這則訊息的工具結果。〔理由〕§6

1. **這則訊息沒有呼叫工具**：`recommendations` 一律當作空的。`reply` 照用，不換固定文字。玩家問「剛剛第二款適合小孩嗎？」只用文字回答，不出卡片。〔理由〕§6.1；不換固定文字〔Q10〕
2. **「這則訊息的工具結果」**：這則訊息每次查詢回傳的桌遊都算。兩次查詢都有結果時，卡片照查詢先後、再照名次排，最多 3 張。〔Q9〕
3. **`game_id` 不在工具結果裡**：整款丟掉。**`excerpt_ids` 裡不屬於該款這則訊息回傳片段的 ID**：只丟那個 ID。都記 log，不重試、不回錯誤。〔理由〕§6.2
4. 同一個 `game_id` 出現兩次，只留第一筆；`excerpt_ids` 超過 2 個，只留前 2 個合法的。〔Q14〕
5. **卡片順序**由 service 照工具回傳的順序重排，不照 LLM 輸出的順序。〔理由〕§6.3
6. **LLM 至少推薦 1 款、卻全部被丟掉**：回固定文字 B（§12.6），記 log。〔理由〕§6.4、〔API〕§3
7. **卡片內容**〔理由〕總覽、〔API〕§1、§7：
   - `game`：從工具結果（資料庫）填，不用 LLM 寫的數字。
   - `reason`：LLM 寫的推薦理由。
   - `excerpts`：照 `excerpt_ids` 的順序，從工具結果填 `id`、`text`、`language`。該款沒有被引用的片段時是空陣列。

### 12.5 放寬的條件

- 這則訊息第 1 次查詢 0 款，第 2 次查詢放寬了時長或年齡其中一項，就標成放寬。〔理由〕§6.5
- 「放寬」：`max_minutes` 拿掉或變大、`min_minutes` 拿掉或變小，標 `playtime`；`youngest_age` 拿掉或變大，標 `age`。
- 已知限制：上一則訊息已經放寬、這則訊息第 1 次查詢就沒帶該條件時，不會標出；卡片仍顯示實際時長與年齡，接受。〔理由〕§6.5
- 時長與年齡同時放寬時，標 `playtime`（放寬順序的第一項）；沒有卡片時一律是 `null`。〔Q14〕

### 12.6 固定文字與例外

| 情況 | service 怎麼做 | API 回應 | 出處 |
|---|---|---|---|
| 任一次 respond 拋 `LLMOutputRejected`（拒答、內容過濾、截斷、不是合法 JSON） | 固定文字 A：「這則訊息我沒辦法回答，請換個說法再試一次。」 | 201，回請求帶來的舊 id | 〔API〕§3、〔提案 §5〕 |
| 模型不照約定回應（§12.2） | 同上 | 同上 | 〔Q11〕 |
| 推薦全部被丟掉（§12.4 第 6 點） | 固定文字 B：「這次推薦出了問題，請再說一次你的需求。」 | 同上 | 〔API〕§3、〔理由〕§6.4 |
| `LLMConversationNotFound` | 轉成 404 錯誤 | 404 `GAMES_ADVISOR_CONVERSATION_NOT_FOUND` | 〔API〕§2 |
| `LLMUnavailable`（包括 fake 沒給腳本） | 轉成 503 錯誤 | 503 `GAMES_ADVISOR_UNAVAILABLE` | 〔API〕§2、〔LLM 設定〕§4 |
| `EmbeddingError`（包括 `EmbeddingUnavailable`） | 同上，不降級成只用結構化分數 | 同上 | 〔API〕§2、〔提案 §5〕 |
| 其他 `LLMError` | 不攔截 | 500 `INTERNAL_ERROR` | 〔提案 §5〕 |

- 固定文字的回應：`reply` 是固定文字、`relaxed_constraint` 是 `null`、`recommendations` 是空陣列；回應不標示是不是固定文字。〔API〕§3
- 回舊 id 代表這則訊息不算進對話：Agent 不記得這段失敗的往返，中途的工具呼叫也不會留下沒送回結果的紀錄。第一則訊息就回 `null`。〔API〕§3
- 404、503 用 `core/errors.py` 的 `AppError` 拋出，由既有的錯誤處理器轉成統一的錯誤格式（AGENTS.md §4.3）。
- log：每次 respond 的 token 用量〔提案 §3.1〕；丟掉的 `game_id`、`excerpt_ids`；換成固定文字的原因〔理由〕§6；向量模型不同（§11.6）。

### 12.7 service 的測試

假的 repository（固定回傳幾款假桌遊）、`FakeLLMProvider(responses=[...])`、`FakeEmbeddingProvider`。〔驗收〕§1、〔提案 §6〕

| 情境 | `FakeLLMProvider` 的腳本 | 預期結果 |
|---|---|---|
| 沒有人數，追問 | 1. 最終輸出（追問、沒有推薦） | respond 1 次；沒有查詢；回新的 id；沒有卡片 |
| 一般推薦 | 1. 查詢 `players=4` 2. 最終輸出推薦 3 款 | respond 2 次；第 2 次的 input 是工具結果、`previous_response_id` 是第 1 次的 id；3 張卡片 |
| 每次都重送 | 同上 | `fake.calls` 每次都有同樣的 instructions 與工具定義 |
| 接續對話 | 請求帶上一則的 id | 第 1 次 respond 的 `previous_response_id` 是它 |
| 放寬時長 | 1. 查詢 `max_minutes=15` → 0 款 2. 查詢 `max_minutes=30` → 2 款 3. 最終輸出 | 第 3 次是 `allow_tool_calls=False`；`relaxed_constraint` 是 `playtime` |
| 放寬年齡 | 1. 查詢 `youngest_age=6` → 0 款 2. 拿掉 `youngest_age` → 有結果 3. 最終輸出 | `age` |
| 第 2 次查詢只換了偏好 | 1. 0 款 2. 只改 `prefer_tags` 3. 最終輸出 | `null` |
| 第 1 次就有結果 | 1. 查詢 2. 最終輸出 | `null` |
| 兩次都 0 款 | 1. 0 款 2. 0 款 3. 最終輸出（沒有推薦） | 沒有卡片；`null` |
| 第 3 次仍要求查詢 | 1. 查詢 2. 查詢 3. 查詢 | 只查 2 次；固定文字 A；回舊 id〔Q11〕 |
| 人數 50 | 1. 查詢 `players=50` 2. 最終輸出（請玩家確認人數） | 沒有呼叫 repository 的查詢；第 2 次的 input 是錯誤；回 `reply` |
| `game_id` 不在工具結果 | 1. 查詢回 A、B 2. 推薦 A、X | 只有 A 的卡片；log 有 X |
| 片段屬於別款 | 1. 查詢 2. A 的 `excerpt_ids` 有 B 的片段 | A 的卡片只少那一段；log |
| 全部被丟掉 | 1. 查詢 2. 只推薦 X | 固定文字 B；回舊 id；沒有卡片；log |
| 沒有查詢卻附推薦 | 1. 最終輸出附 1 款推薦 | 沒有卡片；`reply` 照用；回新的 id〔Q10〕 |
| 卡片順序 | 1. 查詢回 A、B、C 2. 推薦 C、A、B | 卡片是 A、B、C |
| 兩次查詢都有結果 | 1. 回 A、B 2. 回 C、D 3. 推薦 D、A | 卡片是 A、D〔Q9〕 |
| 重複推薦同一款 | 1. 查詢 2. 推薦 A、A | 1 張卡片〔Q14〕 |
| 卡片內容 | 1. 查詢 2. LLM 寫的推薦附錯誤的人數 | `game` 的欄位等於假 repository 的資料；`excerpts` 只有 `id`、`text`、`language`，順序照 `excerpt_ids` |
| 第 1 次拋 `LLMOutputRejected` | 先送一則取得 `fake_resp_1`，再帶它送；1. 例外 | 固定文字 A；回 `fake_resp_1` |
| 查詢後才拋 `LLMOutputRejected` | 1. 查詢 2. 例外 | 同上 |
| 第一則訊息就固定文字 | `previous_response_id` 是 null；1. 例外 | `response_id` 是 null |
| 對話過期 | 請求帶 fake 沒產生過的 id | 404 `GAMES_ADVISOR_CONVERSATION_NOT_FOUND` |
| `LLMUnavailable` | 1. 例外 | 503 `GAMES_ADVISOR_UNAVAILABLE` |
| fake 沒給腳本 | `responses=None` | 503 |
| `embed` 拋 `EmbeddingUnavailable` | 1. 查詢帶 `preference_text` | 503 |
| 其他 `LLMError` | 1. 例外 | 例外往上拋 |
| 角色 | 用 player、shop_staff、admin 各呼叫一次 | 都成功 |

## 13. API：`POST /api/v1/advisor/messages`

### 13.1 請求與回應

〔API〕§1。成功回 201。後端不存對話，所以沒有 GET，也沒有列出對話的端點。

請求：

```json
{"content": "我們 4 個人", "previous_response_id": null}
```

| 欄位 | 規則 |
|---|---|
| `content` | 去掉前後空白後 1–500 字；送給 LLM 的是去掉空白後的文字 |
| `previous_response_id` | 上一則回應的 `response_id`；新對話給 `null`；空字串回 422〔Q14〕 |

回應：

```json
{
  "response_id": "resp_…",
  "reply": "幫你找到 3 款適合 4 個人、輕鬆聊天的桌遊。",
  "relaxed_constraint": null,
  "recommendations": [
    {
      "game": {
        "id": 1, "name": "範例桌遊甲",
        "min_players": 2, "max_players": 4,
        "min_playtime": 30, "max_playtime": 45,
        "min_age": 10, "weight": 1.85
      },
      "reason": "規則簡單、不燒腦，符合你想要的輕鬆路線；心得提到一局節奏很快。",
      "excerpts": [{"id": "<uuid>", "text": "……", "language": "zh-TW"}]
    }
  ]
}
```

| 欄位 | 規則 | 出處 |
|---|---|---|
| `response_id` | 見 §13.2 | 〔API〕§3 |
| `relaxed_constraint` | `playtime`、`age` 或 `null`；整則訊息一個值 | 〔API〕§1、§12.5 |
| `recommendations` | 最多 3 筆，照工具回傳的順序；追問、離題、查無結果、固定文字時是空陣列 | 〔API〕§1 |
| `game` | 8 個欄位，名稱跟著 `games`（§3.1）；`id` 是整數，例如 `1`；`weight` 回原值 | 〔API〕§1；`weight` 原值〔Q14〕；`id` 型別〔整數編號〕 |
| `excerpts` | 只有 `id`、`text`、`language`；不回 `title`、`site_name`、`source_url` | 〔API〕§7 |

- 不串流：整則訊息一次回來。〔API〕§4

### 13.2 錯誤與 `response_id`

| 情況 | 狀態碼 | `error.code` | `response_id` | 出處 |
|---|---|---|---|---|
| 一般回覆：追問、推薦、離題、查無結果 | 201 | — | 新的 id | 〔API〕§3 |
| 固定文字：拒答、內容過濾、模型不照約定 | 201 | — | 請求帶來的舊 id（第一則訊息就是 `null`） | 〔API〕§3 |
| 固定文字：推薦全部被丟掉 | 201 | — | 同上 | 〔API〕§3 |
| 欄位錯誤（空白、超過 500 字、缺欄位） | 422 | `VALIDATION_ERROR`（框架預設） | 前端沿用原本的 id | 〔API〕§2 |
| 未登入（只在 `AUTH_MODE=jwt`） | 401 | `UNAUTHENTICATED`（現有） | 同上 | 〔API〕§2、§5 |
| 對話過期、id 錯、別的 Foundry 產生的 id | 404 | `GAMES_ADVISOR_CONVERSATION_NOT_FOUND` | 前端清空，回到 `null` | 〔API〕§2、〔LLM 設定〕§5 |
| Azure 暫時連不上（LLM 或 embedding）、沒設定模型 | 503 | `GAMES_ADVISOR_UNAVAILABLE` | 前端沿用原本的 id | 〔API〕§2、〔LLM 設定〕§4 |
| 其他程式錯誤 | 500 | `INTERNAL_ERROR`（現有） | 同上 | 〔API〕§2 |

- LLM 和 embedding 共用一個 503 錯誤碼，因為前端的處理方式一樣。〔API〕§2
- 503 不在 AGENTS.md §4.3 的錯誤狀態碼清單裡；組員已同意補進去（§18）。

### 13.3 權限

- 玩家、店家人員、管理員都能用：service 呼叫 `require_role(user, "player", "shop_staff", "admin")`。沒有 403。〔API〕§5
- §7.2 的「沒有權限」情境就是未登入，回 401；只有 `AUTH_MODE=jwt` 會發生，開發模式沒帶標頭會用預設的測試玩家。〔API〕§5
- 後端不檢查 `response_id` 屬於哪位使用者。〔ADR 0001〕

### 13.4 router 的測試

`TestClient`；LLM 用 `FakeLLMProvider` 的腳本、embedding 用 `FakeEmbeddingProvider`、repository 換成假的；角色用 `as_player`、`as_shop_staff`、`as_admin`（AGENTS.md §4.5）。

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 推薦 | `POST`，`content="我們 4 個人，想輕鬆聊天"`、`previous_response_id=null`；腳本：查詢＋推薦 | 201；新的 `response_id`；卡片有 `game` 的 8 個欄位、`reason`、`excerpts`（只有 `id`、`text`、`language`）；`relaxed_constraint` 是 `null` |
| 追問 | 腳本：直接回最終輸出 | 201；`recommendations` 是空陣列 |
| 放寬時長 | 腳本：0 款、放寬後有結果、最終輸出 | 201；`relaxed_constraint` 是 `playtime` |
| 接續對話 | `previous_response_id` 是上一則回的 id | 201；fake 收到這個 id |
| 前後有空白 | `content="  4 人  "` | 201；LLM 收到 `4 人` |
| 剛好 500 字 | 同上 | 201 |
| 只有空白 | `content="   "` | 422 `VALIDATION_ERROR`；沒有呼叫 LLM |
| 501 字 | 同上 | 422 |
| 沒有 `content` | 同上 | 422 |
| `previous_response_id` 是空字串 | 同上 | 422〔Q14〕 |
| 未登入 | `AUTH_MODE=jwt`，不帶 token | 401 `UNAUTHENTICATED` |
| 玩家、店家人員、管理員 | 各送一次 | 都是 201 |
| 對話過期 | `previous_response_id="resp_unknown"` | 404 `GAMES_ADVISOR_CONVERSATION_NOT_FOUND` |
| LLM 連不上 | 腳本：`LLMUnavailable` | 503 `GAMES_ADVISOR_UNAVAILABLE` |
| 沒設定模型 | `FakeLLMProvider()`，沒給腳本 | 503 `GAMES_ADVISOR_UNAVAILABLE` |
| embedding 連不上 | `FakeEmbeddingProvider(error=EmbeddingUnavailable())`，查詢帶 `preference_text` | 503 `GAMES_ADVISOR_UNAVAILABLE` |
| 其他 LLM 錯誤 | 腳本：`LLMError` | 500 `INTERNAL_ERROR` |
| 拒答 | 先送一則取得 `fake_resp_1`，再帶它送；腳本：`LLMOutputRejected` | 201；`reply` 是固定文字 A；`response_id` 是 `fake_resp_1`；沒有卡片 |
| 推薦全部被丟掉 | 腳本：查詢＋推薦不在結果裡的 `game_id` | 201；固定文字 B；回請求帶來的 id |
| 第一則訊息就固定文字 | `previous_response_id=null`；腳本：`LLMOutputRejected` | 201；`response_id` 是 `null` |

## 14. 前端

只做 `data/`、`state/`、`prototypes/` 與交接說明，不碰 `pages/` 與 `app/theme/`（AGENTS.md §5.4、§9）。

### 14.1 `data/`（`frontend/lib/domains/games_advisor/data/`）

- DTO 用 `freezed` + `json_serializable`，JSON 對應 `snake_case`（AGENTS.md §5.3）：請求（`content`、`previousResponseId`）、回應（`responseId`、`reply`、`relaxedConstraint`、`recommendations`）、卡片（`game`、`reason`、`excerpts`）、桌遊（§13.1 的 8 個欄位）、心得片段（`id`、`text`、`language`）。
- repository 一個方法：送出訊息，呼叫 `POST /api/v1/advisor/messages`。用 `core/api` 的 `dioProvider`；錯誤轉成既有的 `ApiException`（斷線、逾時是 `NETWORK_ERROR`）。
- 等待上限 100 秒：比後端最壞的 3 × 30 = 90 秒長。〔部署〕§6、〔API〕§4。做法：只在這個請求設定 dio 的接收逾時，寫在 `games_advisor/data/`，不改 `core/api`（永傑擁有）。〔Q14〕

### 14.2 `state/`（`frontend/lib/domains/games_advisor/state/`）

照草圖第一個 `<script>` 改成 Riverpod，參考畫面與正式頁面共用。〔API〕§6

| 狀態 | 型別 | 說明 |
|---|---|---|
| `messages` | 清單 | 玩家的訊息：文字。推薦 Agent 的訊息：`reply`、卡片、放寬的條件 |
| `responseId` | 字串或 null | 前端保管的最新 `response_id`，下一則訊息帶回去 |
| `status` | `idle`、`sending` | |
| `draft` | 字串 | 輸入框內容 |
| `notice` | null、`expired`、`unavailable`、`unauthenticated` | 錯誤提示 |

| 方法 | 做什麼 |
|---|---|
| `editDraft(text)` | 改輸入框內容 |
| `sendMessage(content)` | 送出。輸入框的送出鈕傳 `draft`；範例按鈕傳範例文字 |
| `startNewConversation()` | 回到初始狀態，不呼叫 API |
| `canSend` | 不在送出中，而且去掉空白後 1–500 字 |
| `canStartNew` | 不在送出中，而且有訊息、提示或輸入框內容 |

送出與回應：

1. 送出：不符合 `canSend` 就不動作。符合時，玩家訊息加進 `messages`，`status` 改成 `sending`，清空 `draft` 與 `notice`，帶去掉空白的文字與 `responseId` 呼叫 repository。
2. 201：`status` 回到 `idle`，`responseId` 換成回應的值（固定文字時就是舊 id），推薦 Agent 的訊息加進 `messages`。
3. 404 `GAMES_ADVISOR_CONVERSATION_NOT_FOUND`：回到初始狀態，剛剛那句放回 `draft`，`notice` 是 `expired`。
4. 401 `UNAUTHENTICATED`：拿掉剛剛那則玩家訊息、放回 `draft`，`notice` 是 `unauthenticated`，`responseId` 不變。
5. 其他錯誤（503、500、422、`NETWORK_ERROR`）：同上，`notice` 是 `unavailable`。
6. 送出中按「開始新對話」：不動作，避免回應接到新的對話上。〔Q14〕

- 不把訊息存進瀏覽器，重新整理就是新對話。〔API〕§6、〔ADR 0001〕

`state/` 的測試（`flutter test`，假的 repository）：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 新對話 | 建立 | `messages` 空、`responseId` null、`idle`、`draft` 空、`notice` null；不能送出、不能開始新對話 |
| 輸入 `"  4 人  "` | `editDraft` | 可以送出 |
| 只有空白、501 字 | `editDraft` | 不能送出；剛好 500 字可以 |
| 送出 | `sendMessage` | repository 收到 `4 人` 與 null；`sending`；玩家訊息加進去；`draft`、`notice` 清空 |
| 送出中再送 | `sendMessage` | 不呼叫 repository |
| 收到推薦 | repository 回 201 | `idle`；`responseId` 換新；推薦 Agent 的訊息有 `reply`、卡片、放寬的條件 |
| 第二則訊息 | `sendMessage` | repository 收到上一則的 `responseId` |
| 收到固定文字 | repository 回舊 id | `responseId` 是舊 id；訊息照常顯示 |
| 對話過期 | repository 拋 404 | 回到初始狀態；`draft` 是剛剛那句；`notice` 是 `expired` |
| 暫時無法回應 | repository 拋 503 | 拿掉剛剛那則；`draft` 是那句；`notice` 是 `unavailable`；`responseId` 不變 |
| 500、422、斷線 | 同上 | 同上 |
| 未登入 | repository 拋 401 | 同上，`notice` 是 `unauthenticated` |
| 開始新對話 | `startNewConversation` | 回到初始狀態；沒有呼叫 repository |
| 送出中開始新對話 | 同上 | 不動作〔Q14〕 |
| 過期後 | — | 可以開始新對話（有提示與輸入框內容） |
| 範例按鈕 | `sendMessage("我們 4 個人，想輕鬆聊天")` | 和送出相同 |

`data/` 的測試：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 回應有 1 張卡片、`relaxed_constraint` 是 `playtime` | 解析 JSON | 每個欄位都對到 `camelCase` 欄位 |
| `relaxed_constraint` 是 null、`recommendations` 是空的 | 同上 | 解析成功 |
| 送出 | 呼叫 repository | `POST /api/v1/advisor/messages`，body 是 `content`、`previous_response_id`；接收逾時 100 秒 |
| 後端回錯誤格式 | 同上 | 拋 `ApiException`，`code` 是後端的 `error.code` |

### 14.3 參考畫面（`frontend/lib/prototypes/games_advisor/`）

只用 Flutter 預設元件，不套主題、不做 RWD。路由 `/proto/games_advisor`，只在 `SHOW_PROTOTYPES=true` 時出現（AGENTS.md §5.4）。路由表在 `frontend/lib/app/router.dart`（永傑擁有），MR 要 @ 永傑（AGENTS.md §2.3）。

元件〔API〕§6：

| 元件 | 行為 | `state/` |
|---|---|---|
| AppBar「開始新對話」 | 清空訊息與 `response_id`，不呼叫 API，不跳確認視窗；不能開始新對話時停用 | `startNewConversation()`、`canStartNew` |
| 空畫面 | 說明文字＋3 個範例按鈕，點了直接送出：「我們 4 個人，想輕鬆聊天」「2 個人約會玩」「6 個人，30 分鐘內玩完」 | `sendMessage(content)` |
| 訊息列表 | 玩家與推薦 Agent 的訊息；推薦 Agent 的訊息下面接放寬提示與卡片 | `messages` |
| 放寬提示 | 卡片上方一行「以下放寬了「時長」條件」（或「年齡」），不是每張卡片各標一次 | — |
| 推薦卡片 | 繁中名稱；「2–4 人 · 30–45 分鐘 · 10 歲以上 · 難度 1.9 / 5」（最少等於最多時只寫一個數字；難度四捨五入到小數 1 位〔Q14〕）；推薦理由；「心得片段（n）」預設摺疊，點開看原文，英文片段旁標「英文」；沒有片段時不顯示這一行 | — |
| 輸入框＋送出 | 顯示字數；Enter 送出、Shift+Enter 換行；不能送出時停用 | `editDraft`、`sendMessage(draft)`、`canSend` |
| 規則問答連結 | 輸入框下方固定一行「想問規則或玩法？到規則問答」；`rules_qa` 還沒有頁面，先留位置 | — |

狀態〔API〕§6：

| 狀態 | 顯示 |
|---|---|
| 載入中 | 推薦 Agent 的位置顯示「正在找桌遊…」，輸入框與按鈕停用 |
| 沒有資料（新對話） | 說明文字＋範例按鈕 |
| `expired` | 清空畫面，顯示「對話已失效，請開始新對話」，剛剛那句在輸入框 |
| `unavailable` | 剛剛那句從畫面拿掉、放回輸入框，顯示「推薦 Agent 暫時無法回應，請再送一次」 |
| `unauthenticated` | 「請先登入再使用推薦 Agent」 |
| 追問、離題、查無結果、固定文字 | 只有文字，沒有卡片 |

- 沒有金鑰（`LLM_PROVIDER=fake`）時送出都是 503，看不到卡片；永傑看參考畫面與交接說明的截圖。〔LLM 設定〕§4

### 14.4 交接說明（`docs/handoff/games_advisor.md`）

照 `docs/handoff/_template.md` 寫：

| 段落 | 內容 |
|---|---|
| 1. 頁面清單 | 一頁：推薦 Agent，`/proto/games_advisor` |
| 2. 按鈕與欄位 | §14.3 的元件表，加上後端 API 欄：送出與範例按鈕對應 `POST /api/v1/advisor/messages`，其他不呼叫 API |
| 3. 狀態顯示 | §14.3 的狀態表。範本的「沒有權限（403）」改寫成：這個功能沒有 403，未登入是 401 |
| 4. 截圖 | 參考畫面做好後截圖：空畫面、載入中、推薦卡片（片段摺疊與展開）、放寬提示、對話已失效、暫時無法回應。放在 `docs/handoff/images/games_advisor/`。卡片要用真的模型才截得到 |
| 5. 備註 | 前端等待上限 100 秒；不存進瀏覽器；只顯示心得片段原文、不顯示來源（〔API〕§7，立倫接受著作權法第 64 條的風險）；規則問答連結等 `rules_qa` 有頁面再接 |

- MR 加 `needs-ui` 標籤，@ 永傑（AGENTS.md §5.4）。

## 15. 評估題組 `eval`

### 15.1 怎麼執行

```
uv run python -m app.domains.games_advisor.commands eval <eval_cases.json> --out <報告> [--repeat N] [--no-judge]
```

- 在本機開發資料庫上執行：先跑完匯入桌遊與心得管線，用真的 16 款、標籤與向量，連真的 Azure。不進 CI、不擋合併。〔驗收〕§3、§4
- 直接呼叫 service，不經過 HTTP API（API 回應裡沒有工具參數）。真的 LLM provider 外面包一層記錄器，記下每次呼叫模型的內容和回應，從裡面取工具參數。〔驗收〕§4
- 對話用的 provider 和 API 相同（`LLM_MODEL`、`LLM_REASONING_EFFORT`、`LLM_TIMEOUT_SECONDS`），不是批次的設定。〔部署〕§1
- 評審（§15.6）另外建一個 provider，用批次的設定（§7.2 第 4 點）；加 `--no-judge` 就不跑評審，也不建這個 provider。〔評審〕

開始前檢查，不通過就拒絕執行（結束碼 1），不呼叫模型：

1. `LLM_PROVIDER=fake`：印出「需要真的模型，請設定 LLM_*」（§7.2 第 3 點）。`local` 不擋，遇到 `respond` 會拋 `NotImplementedError`。〔LLM 設定〕§4
2. `games_advisor` 有任何心得摘要向量或心得片段的模型和目前 `GAMES_ADVISOR_EMBEDDING_MODEL` 不同：印出是哪幾款，提醒重跑 `summarize-reviews`、`build-excerpts`。〔改版〕§5
3. 沒有向量的桌遊只提醒，不拒絕。〔Q14〕
4. 報告路徑已存在。〔Q14〕

### 15.2 `eval_cases.json`

位置 `backend/tests/games_advisor/eval_cases.json`，進 repo；只有立倫寫的玩家訊息和預期結果，沒有心得原文。〔驗收〕§9

```json
{
  "cases": [
    {
      "id": "relax-playtime-01",
      "demo": false,
      "turns": [
        {
          "player": "我們 4 個人，15 分鐘內要玩完，想要歡樂一點的",
          "expect": {
            "action": "recommend",
            "tool_args": {"players": 4, "max_minutes": 15, "prefer_tags": ["laughter"]},
            "relaxed_constraint": "playtime",
            "manual": ["回覆有說明放寬了時長"]
          }
        }
      ]
    }
  ]
}
```

外層 `{"cases": [...]}`、`demo` 欄位、`exclude_bgg_ids` 的寫法〔Q14〕；`expect` 的欄位〔驗收〕§5：

| 欄位 | 意思 | 程式怎麼比對 | 計入 |
|---|---|---|---|
| `action` | `follow_up`、`recommend`、`off_topic` | `recommend` 要有卡片；另外兩種要沒有卡片（兩者的差別由 `manual` 人工檢查） | 條件分 |
| `tool_args` 的 `players`、`max_minutes`、`min_minutes`、`youngest_age` | 條件 | 數值相等；寫 `null` 代表必須沒帶〔Q14〕 | 條件分 |
| `tool_args` 的 `weight_min`、`weight_max` | 難度 | 數值相等 | 偏好分 |
| `tool_args` 的 `prefer_*`、`avoid_*` | 偏好 | 有沒有包含：模型多帶其他值不算錯 | 偏好分 |
| `tool_args` 的 `exclude_bgg_ids` | 排除清單，用 BGG ID 寫 | 換成桌遊 `id` 後檢查有沒有包含 | 條件分 |
| `relaxed_constraint` | `playtime`、`age`、`null` | 相等 | 條件分 |
| `expect_any` | 合適的桌遊（BGG ID） | 卡片裡至少出現一款 | 偏好分 |
| `forbid` | 不能出現的桌遊（BGG ID） | 卡片裡一款都不能出現 | 條件分 |
| `manual` | 人工檢查提示 | 報告列成勾選框 | 人工項目 |

- 只寫這一輪要檢查的欄位。`tool_args` 比對這一輪的第 1 次工具呼叫（玩家原本說的條件）；寫了 `tool_args` 卻沒有呼叫工具，算不符合。〔驗收〕§5
- 桌遊用 BGG ID、標籤用詞彙表代碼指定。〔驗收〕§5
- 題目：10 題，5 組行為各 2 題，其中 3 題是 Demo 題（每款 Demo 遊戲一題）。心得管線跑完、詞彙表定好後才寫，AI 可以先起草，立倫審核定稿。〔驗收〕§7

### 15.3 計分與次數

〔驗收〕§6、§8：

- 三種分數各算通過比例，例如「條件分 38/40」：條件分、偏好分、人工項目（人工項目由立倫在報告勾選後自己統計，不混進前兩種）。
- 評審建議（§15.6）不算進三種分數，也不影響 Demo 題過不過。〔評審〕
- 某一輪不符合預期時，這題停在那一輪，後面的輪次標成「未執行」。〔驗收〕§5
- 細節〔Q14〕：
  - 每個寫在 `expect` 的項目算 1 分；「未執行」輪次的項目算沒通過，分母固定，不同次執行的分數才比得起來。
  - 該輪拿到 503、500 或固定文字，算不符合，停在那一輪。
- Demo 題各跑 3 次，條件分、偏好分 3 次都全過，人工項目也 3 次都勾過，才算過。其他 7 題各跑 1 次，只記分數，不設及格線。
- `--repeat N`：非 Demo 題各跑 N 次（預設 1）；Demo 題固定 3 次。〔Q14〕
- 結束碼：0 跑完（不論分數）；1 拒絕執行。〔Q14〕

### 15.4 報告

- Markdown，寫到 `--out` 指定的 repo 外路徑；報告裡有心得片段原文，所以不進 repo。〔驗收〕§9
- 內容：每題每輪的玩家訊息、`reply`、卡片（名稱、推薦理由、片段原文）、工具參數、每個項目過或不過、`manual` 的勾選框；三種分數；Demo 題過了沒；token 用量（`LLMResponse` 的 `input_tokens`、`output_tokens` 加總）。〔驗收〕§8、〔提案 §3.1〕
- 評審建議（§15.6）：開頭印出對話與評審的模型名稱，每張卡片下方一行評審建議，結尾有評審統計。token 用量只算對話，不含評審。〔評審〕
- MR 說明只貼三種分數、token 用量與評審統計，不貼回覆內容，放在 §7.4 的表格外面。〔驗收〕§3、§9、〔評審〕

### 15.5 測試（進 CI）

〔驗收〕§10、〔改版〕§3。用 `FakeLLMProvider` 的腳本與假的 repository，不連 Azure：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| repo 裡的 `eval_cases.json` | 檢查格式 | 每題有 `id` 且不重複；`action` 是三種之一；`expect` 沒有不認得的欄位 |
| 同上 | 和 `tag_vocabulary.json` 比 | 用到的每個代碼都在詞彙表裡 |
| 預期 `players: 4`，實際 4／5 | 比對 | 過／不過 |
| 預期 `prefer_tags: [laughter]`，實際 `[laughter, x]` | 比對 | 過 |
| 預期 `max_minutes: null`，實際 60 | 比對 | 不過〔Q14〕 |
| 第 1 次查詢 `max_minutes=15`、第 2 次 30，預期 15 | 比對 | 過（比第 1 次） |
| `exclude_bgg_ids` | 比對 | 換成 `id` 後比對 |
| `action: recommend` 但沒有卡片 | 比對 | 不過 |
| `expect_any` 有一款在卡片裡、`forbid` 有一款在卡片裡 | 比對 | 前者過、後者不過 |
| 3 輪，第 1 輪不符合 | 執行 | 第 2、3 輪標「未執行」，項目算沒通過 |
| 某一輪拿到 503 或固定文字 | 執行 | 該輪不符合，停下〔Q14〕 |
| 各種結果 | 計分 | 條件分、偏好分、人工項目數各自正確 |
| Demo 題 3 次中第 2 次不過 | 執行 | Demo 題不過 |
| `--repeat 2` | 執行 | 非 Demo 題各 2 次、Demo 題 3 次〔Q14〕 |
| `--out` | 執行 | 報告寫到指定路徑；有 token 用量；`manual` 是勾選框 |
| 報告路徑已存在 | 執行 | 結束碼 1；沒有呼叫 LLM〔Q14〕 |
| `LLM_PROVIDER=fake` | 執行 | 結束碼 1（§7.2 的共用測試） |
| 有向量的模型和目前設定不同 | 執行 | 結束碼 1；印出哪幾款；沒有呼叫 LLM |
| 沒有權限 | — | 不適用：本機指令 |

### 15.6 評審建議

〔評審〕。再呼叫一次模型，檢查每張卡片的推薦理由有沒有寫出依據裡沒有的內容。這是 §12.1「推薦理由」那一列裡，程式比對不出來的部分。結果只當建議：立倫勾選 `manual` 時參考，仍由立倫做最後判斷。

**送什麼給評審**

- 每張卡片呼叫 1 次，一次只看一張卡片，不做兩兩比較。
- 用 `generate_json`，輸入是這張卡片的三樣東西：
  1. 推薦理由（卡片的 `reason`）。
  2. 卡片上顯示的心得片段原文（卡片的 `excerpts`）。工具有回傳、但沒被引用的片段不給：玩家只看得到卡片上的。
  3. 這款桌遊在這則訊息的工具結果裡的 `matched_preferences`、`matched_avoids`（§11.7），從記錄器取（§15.1）；兩次查詢都回傳這一款時，兩次的都給。對話規則允許推薦理由寫命中的偏好（§12.1），只給片段會把合規的內容判成沒有依據。
- 評審規則是程式裡的一段固定文字：只判斷推薦理由的每個說法能不能在上面的依據裡找到；找不到的逐條列出；不評文筆，也不評推薦得好不好。
- 輸出用 strict JSON schema（名稱 `advisor_reason_check`）：

  ```json
  {"unsupported": ["理由說「適合新手」，片段和命中的偏好都沒有提到"]}
  ```

  空陣列是「有依據」，有內容是「有疑慮」。

**用哪個模型**

- 評審的 provider 用批次的設定（§7.2 第 4 點），和對話的 provider 分開建立：對話的只呼叫 `respond`，評審的只呼叫 `generate_json`。
- `LLM_BATCH_MODEL` 留空時照 §7.2 退回 `LLM_MODEL`，照常執行；報告開頭多一行「評審和對話是同一個模型」。

**不送評審、評審出錯**

| 情況 | 怎麼做 | 報告寫 |
|---|---|---|
| 卡片沒有心得片段 | 不呼叫評審 | 未評審：沒有引用心得片段 |
| 推薦理由是空字串 | 不呼叫評審 | 未評審：推薦理由是空的 |
| 沒有卡片的輪次（追問、離題、固定文字、未執行） | 不呼叫評審 | — |
| `--no-judge` | 整次都不呼叫評審 | 開頭寫「這次沒有跑評審」 |
| `LLMOutputRejected` | 重試 1 次（§7.2 第 6 點的共用函式），仍然失敗就放棄這張 | 評審失敗＋原因 |
| 其他 `LLMError`（包括 `LLMUnavailable`） | 不重試，放棄這張 | 評審失敗＋原因 |

- 和 §7.2 第 6 點不同的地方：那裡「其他 `LLMError`」不攔截、整個指令失敗；評審一律攔下來。對話的 token 已經花了，評審出錯不該讓整份報告消失。
- 評審失敗不影響其他卡片、分數與結束碼（§15.3）。

**報告**

- 開頭：對話模型與評審模型的名稱。
- 每張卡片下方一行「評審建議」：有依據／有疑慮（列出 `unsupported` 的每一筆）／未評審／評審失敗。
- 結尾：四種標示各幾張，以及一句「評審建議不算分，以人工勾選為準」。
- 評審的 token 不列入報告的 token 用量：`generate_json` 只回傳內容、不回傳用量〔提案 §3.2〕，要算就得改整合層。報告只印評審呼叫了幾次，實際花費到 Azure 看。
- 評審也會判錯。第一次跑完後，立倫對照評審建議和自己的勾選，把一致的張數寫進 MR 說明。

測試（進 CI）。對話用 `FakeLLMProvider(responses=[...])`，評審用另一個 `FakeLLMProvider(json_outputs=[...])`：

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 1 張卡片，評審回 `unsupported: []` | 執行 | 該卡片寫「評審建議：有依據」 |
| 評審回 `unsupported` 有 1 筆 | 執行 | 寫「評審建議：有疑慮」並列出那 1 筆 |
| 同上 | 看評審的 fake 收到的 `input` | 有推薦理由、卡片上的片段原文、`matched_preferences`、`matched_avoids`；沒有未被引用的片段 |
| 同一款在兩次查詢都有回傳 | 同上 | 兩次的 `matched_preferences`、`matched_avoids` 都有 |
| 一輪 3 張卡片 | 執行 | 評審呼叫 3 次，每次只有 1 張卡片的內容 |
| 同一段對話，評審回「有疑慮」或「有依據」 | 各執行一次 | 條件分、偏好分、人工項目數、Demo 題過不過都相同 |
| 卡片沒有心得片段 | 執行 | 不呼叫評審；寫「未評審：沒有引用心得片段」 |
| 推薦理由是空字串 | 執行 | 不呼叫評審；寫「未評審：推薦理由是空的」 |
| 追問、離題、固定文字的輪次 | 執行 | 不呼叫評審 |
| `--no-judge` | 執行 | 沒有任何 `generate_json` 呼叫；報告寫「這次沒有跑評審」 |
| 評審第 1 次拋 `LLMOutputRejected`、第 2 次正常 | 執行 | 用第 2 次的結果 |
| 評審連 2 次拋 `LLMOutputRejected` | 執行 | 該卡片寫「評審失敗」和原因；其他卡片照常評審；報告照寫；結束碼 0 |
| 評審拋 `LLMUnavailable` | 執行 | 不重試；該卡片寫「評審失敗」；報告照寫；結束碼 0 |
| 評審拋其他 `LLMError` | 執行 | 同上 |
| 對話與評審各一個 provider | 執行 | 對話的 fake 只收到 `respond`；評審的 fake 只收到 `generate_json` |
| `LLM_MODEL=a`、`LLM_BATCH_MODEL=b` | 寫報告 | 開頭印出對話模型 a、評審模型 b |
| `LLM_BATCH_MODEL` 留空 | 寫報告 | 評審模型也是 a；多一行「評審和對話是同一個模型」 |
| 有依據 2 張、有疑慮 1 張、未評審 1 張、評審失敗 1 張 | 寫報告 | 結尾的評審統計是 2／1／1／1 |
| 沒有權限 | — | 不適用：本機指令 |

## 16. 模型、推理強度、逾時

設定欄位見 §4.1，這裡只列對話相關的值〔部署〕：

| 項目 | 值 | 出處 |
|---|---|---|
| 對話模型 | `gpt-5.6-luna`（`LLM_MODEL`） | 〔部署〕§1 |
| 推理強度 | `low`（`LLM_REASONING_EFFORT`） | 〔部署〕§4 |
| 單次 LLM 逾時 | 30 秒（`LLM_TIMEOUT_SECONDS`） | 〔部署〕§6 |
| 一則訊息最壞情況 | 3 次 LLM × 30 秒 = 90 秒 | 〔API〕§4 |
| 前端等待上限 | 100 秒 | 〔部署〕§6 |
| embedding | `text-embedding-3-large`，1536 維 | 〔部署〕§3 |

- 升級路徑：Demo 題用 luna 過不了時，把 `LLM_MODEL` 改成 `gpt-5.6-terra`，換之前、換之後各跑一次評估題組比較，程式不用改。〔部署〕§1

## 17. 整合層

- 介面、例外、fake、設定照[整合層提案](integrations-proposal.md)；測試案例直接用提案第 11 節的表格，這裡不重抄。〔提案 §11〕
- games_advisor 依賴的部分：`respond`（對話）、`generate_json`（歸納詞彙表、上標籤、評估題組的評審）、`generate`（心得摘要）、`embed`；`FakeLLMProvider` 的 `responses`、`json_outputs` 腳本與 `calls`；`FakeEmbeddingProvider` 的 `vectors`、`error`；沒給腳本時拋 `LLMUnavailable`。〔提案 §3、§6〕
- `integrations/llm/`、`integrations/embedding/` 由瑋鋐擁有；誰實作、OpenSpec `llm-provider` 規格的更新放在哪一張，由「[把 spec 拆成 TDD 實作 ticket](issues/22-split-spec-into-tdd-tickets.md)」決定。〔提案 §9〕
- 第一張實作 ticket 要在 Azure 驗證提案第 10 節的 5 件事，排在「建立 Foundry 與三個部署」之後。〔提案 §10〕、〔部署〕§8
- 雲端實作另外有 4 個外部服務測試（§2），在本機確認真的連得上 Azure，範圍見提案 §11.6。`external` 標記已由 #18 註冊在 `backend/pyproject.toml`，不用再加。〔提案 §11.6〕、AGENTS.md 7.6

## 18. 組員已同意的事

下面 5 件事和 AGENTS.md 的規則有出入，或會改到全組的流程。前 4 件 2026-11-09 組員討論後同意；第 5 件 2026-11-10 已由組員寫進 AGENTS.md 7.6（#18）。AI 不改 AGENTS.md（AGENTS.md §2.0）：503 要補進 §4.3 的清單，由組員親手修改 AGENTS.md，以 MR 提出。

| 事項 | 內容 | 出處 |
|---|---|---|
| 503 補進 §4.3 | §4.3 的錯誤狀態碼清單沒有 503；games_advisor 用 503 `GAMES_ADVISOR_UNAVAILABLE` 表示 Azure 暫時連不上 | 〔API〕§2 |
| ADR 0001 | 對話狀態交給 Azure 保存，偏離 §4.2「用 `LLM_PROVIDER` 切換雲端與地端」 | 〔ADR 0001〕 |
| ADR 0002 | 追問與推薦由 LLM 依對話規則決定 | 〔ADR 0002〕 |
| 評估題組的位置 | pytest 仍是合併的唯一標準；評估題組不進 CI、不擋合併，改到對話規則等項目時把分數貼進 MR | 〔驗收〕§3 |
| 外部服務測試不進 CI（已寫進 AGENTS.md） | 外部服務測試（§2）只能放在 `integrations/`，加上 `external` 標記，不在 CI 跑；缺金鑰時直接失敗並說明缺哪個設定；改到 `integrations/` 的 MR 要在說明貼上本機執行 `uv run pytest -m external` 的結果。能用 fake（例如 `FakeAzureTransport`）寫的測試，照樣進 CI | AGENTS.md 7.6（#18）、[ticket 11](../games-advisor-impl/issues/11-agents-md-secret-tests.md) |
