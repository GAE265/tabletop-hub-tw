# 桌遊推薦 Agent + 桌遊 RAG

## Destination

一份 `.scratch/games-advisor/spec.md`，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格，並拆成 TDD 實作 ticket。
範圍：多輪對話推薦、桌遊基本資料、心得標籤的離線批次、檢索比對、後端 API 契約、prototype 頁面與交接說明。

## Notes

- Domain：`games_advisor`（#1 桌遊推薦 Agent，立倫主責）。後端在 `backend/app/domains/games_advisor/`；前端只做 `data/`、`state/`、`prototypes/` 與交接說明（AGENTS.md §5.4）。
- 規則：遵守 `AGENTS.md`（AI 只讀，不得修改）。術語用 AGENTS.md §10 與 `GLOSSARY.md` 的提案區（條件、偏好、標籤、心得）。
- Skills：`grilling` ticket 呼叫 grilling 與 domain-modeling；`research` ticket 呼叫 research；`prototype` ticket 呼叫 prototype。
- 分工：games_advisor 內的程式由立倫寫。`integrations/`（瑋鋐擁有）的介面先由「需要整合層提供哪些介面」提案，誰實作再和瑋鋐談。
- Ticket 的 `Status:` 用 `open`、`claimed`、`resolved`。
- 固定偏好：
  - 不問時程問題，推薦答案也不附日期或天數。
  - 桌遊資料只供推薦使用；不提議共用桌遊目錄或拆出 catalog domain。
  - commit、PR、文件都不加 AI 署名。
  - 不 push、不建 GitHub issue、不開 research 分支。
  - 心得原文、抓取的資料、課程教材內容都不進 repo。
  - BGG 的規定（儲存、快取期限、來源標示）不在立倫的處理範圍：不再開核對 BGG 條款的 ticket，以完成 games_advisor 功能為優先。
  - AI 助理不代抓 robots.txt 擋了 AI 代理的網站（例如 PTT 擋 `Claude-User`），也不繞過 Cloudflare 的阻擋；這類網站由組員用瀏覽器處理。
- 教材表格（git 外）：`團隊專題/99_其他/RAG/games_advisor-rag-materials.md`（`團隊專題/` 是 repo 根目錄下指向團隊專題資料夾的 symlink，已列在 `.git/info/exclude`，不進 git）

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [RAG 教材有哪些可以重用](issues/01-rag-materials-reuse.md)：只取骨架改寫，包括結構化擷取、SQL 篩選後用 pgvector 排序、引用心得 ID；不用 LangChain、FAISS 與課程端點
- [桌遊基本資料從哪裡取得](issues/02-game-data-sources.md)：BGG 欄位最完整（需註冊 token）；Wikidata 是 CC0 但欄位缺漏多；代理商頁只能人工對照。研究中「BGG 禁止用於 AI」的說法已由 ticket 15 更正
- [英文與繁中心得從哪裡取得](issues/03-review-sources.md)：BGG 評分留言量最大，部落格要作者同意，PTT 屬灰色地帶，Reddit、巴哈、Dcard 不行；BGG 的 AI 限制已由 ticket 15 更正
- [核對 BGG 使用條款原文](issues/15-verify-bgg-terms.md)：現行 6.B.iv 允許把 BGG 內容交給 LLM 做摘要、搜尋、回答等一般用途，只禁止大型 AI 公司訓練；本專案視為非商業，收錄約 3–15 款；能不能存進資料庫還沒核對
- [確認可用的 Azure OpenAI 資源](issues/04-azure-openai-resources.md)：另建專題專用的 Foundry，只有立倫使用，課程額度 NTD 2800；已確認 gpt-4.1-mini、gpt-4.1、gpt-4o-mini 支援 structured outputs，gpt-5.6 系列不確定；要部署哪些模型由新 ticket 決定
- [對話狀態存在哪裡](issues/05-conversation-state.md)：交給 Azure Responses API 保存，前端帶 `response_id` 接續；後端不存、不綁使用者、不能回看，Azure 保留 30 天；偏離 §4.2 的地端切換，寫成 ADR 0001（proposed）等組員決定
- [收錄哪些桌遊、存哪些欄位](issues/06-game-coverage-and-fields.md)：15 款（含 Demo 三款）；條件欄位是人數、時長、年齡，偏好欄位是 BGG 的類別、機制、難度；Codex 透過 BGG XML API 產生 repo 外的 JSON，後端匯入指令讀檔寫入
- [Agent 怎麼追問、什麼時候推薦](issues/07-conversation-flow.md)：Agent 依對話規則自己判斷追問或推薦（function calling），程式守三道護欄：人數必填、只推薦工具回傳的桌遊、每則訊息最多呼叫 2 次工具；人數是唯一必要條件，最多推薦 3 款，一律用繁中；查無結果時放寬時長或年齡其中一項，人數不放寬；離題規則也在這張；偏離「程式判斷流程」的取捨寫成 ADR 0002（proposed）
- [標籤詞彙表怎麼定](issues/08-tag-vocabulary.md)：詞彙先從心得歸納，再由立倫審核固定（最多約 30 個），每個標籤有英文代碼、繁中名稱、繁中定義；只描述玩起來的感受，不和條件或 BGG 欄位重複，每個面向只留一個方向；每款的每個標籤有 LLM 給的 0–1 信心分數，給分標準移到心得管線；人工驗證只能刪標籤
- [條件與偏好怎麼比對桌遊](issues/10-matching-strategy.md)：SQL 篩條件；負面偏好優先排後面，再用 RRF 合併結構化分數（標籤信心、類別、機制、難度）與偏好描述對心得摘要的向量相似度，回傳前 3 款；同一個工具再取每款 2 段心得片段當理由出處；embedding 主要為展示 RAG；心得摘要向量放桌遊資料表、心得片段另開一張表，不建索引

## Not yet specified

- 資料表結構：桌遊欄位與向量位置已定，其餘等心得管線決定後才畫得出來（對話不建資料表）。
- 標籤、心得摘要、心得片段要不要定期重跑（包括詞彙表改版、換 embedding 模型後要不要全部重產），怎麼只更新有變動的部分。
- 批次指令部署到 Azure 後在哪裡執行。
- 把所有決定整理成 `spec.md` 與 §7 情境表格。

## Out of scope

- 正式頁面：由永傑依交接說明製作（AGENTS.md §5.4）。
- 推薦時不考慮店家有沒有這款桌遊。
- 地端 LLM：AGENTS.md 列為加分項目，之後再做。
- 語音對話。
