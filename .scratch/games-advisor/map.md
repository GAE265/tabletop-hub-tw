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
  - 這個功能主要展示 Agent 與桌遊 RAG 的應用，準確率不追求最高（2026-11-08 於「[怎麼驗收推薦結果](issues/14-recommendation-acceptance.md)」說明）。
  - 桌遊資料只供推薦使用；不提議共用桌遊目錄或拆出 catalog domain。
  - commit、PR、文件都不加 AI 署名。
  - 不 push、不建 GitHub issue、不開 research 分支。
  - 心得原文、抓取的資料、課程教材內容都不進 repo。
  - BGG 的規定（儲存、快取期限、來源標示）不在立倫的處理範圍：不再開核對 BGG 條款的 ticket，以完成 games_advisor 功能為優先。
  - 開發期間，立倫和組員各用自己的 LLM、embedding 模型與 PostgreSQL，可能各自有一個 Foundry project；最後可能整合成一個 Foundry，也可能維持多個 Foundry 與 PostgreSQL。embedding 的設定與向量不要假設和組員共用（`GAMES_ADVISOR_EMBEDDING_*`）；LLM 用全域 `LLM_*`，換 LLM 不影響已存的資料（2026-11-08 於「[詞彙表改版或換 embedding 模型時怎麼處理](issues/18-vocabulary-and-embedding-revisions.md)」說明，「[LLM 設定也改成 games_advisor 自己的一組嗎](issues/19-games-advisor-llm-settings.md)」改成只限 embedding）。
  - AI 助理不繞過 Cloudflare 的阻擋。robots.txt 擋了 AI 代理的網站（例如 PTT 擋 `Claude-User`、`ChatGPT-User`）：Claude 不代抓；收集心得的 Codex 可以讀（2026-11-08 於「[心得來源走哪條路](issues/16-review-source-decision.md)」決定）。
- 教材表格（git 外）：`團隊專題/99_其他/RAG/games_advisor-rag-materials.md`（`團隊專題/` 是 repo 根目錄下指向團隊專題資料夾的 symlink，已列在 `.git/info/exclude`，不進 git）

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [RAG 教材有哪些可以重用](issues/01-rag-materials-reuse.md)：只取骨架改寫，包括結構化擷取、SQL 篩選後用 pgvector 排序、引用心得 ID；不用 LangChain、FAISS 與課程端點
- [桌遊基本資料從哪裡取得](issues/02-game-data-sources.md)：BGG 欄位最完整（需註冊 token）；Wikidata 是 CC0 但欄位缺漏多；代理商頁只能人工對照。研究中「BGG 禁止用於 AI」的說法已由 ticket 15 更正
- [英文與繁中心得從哪裡取得](issues/03-review-sources.md)：BGG 評分留言量最大，部落格要作者同意，PTT 屬灰色地帶，Reddit、巴哈、Dcard 不行；BGG 的 AI 限制已由 ticket 15 更正
- [核對 BGG 使用條款原文](issues/15-verify-bgg-terms.md)：現行 6.B.iv 允許把 BGG 內容交給 LLM 做摘要、搜尋、回答等一般用途，只禁止大型 AI 公司訓練；本專案視為非商業，收錄約 3–15 款；能不能存進資料庫還沒核對
- [確認可用的 Azure OpenAI 資源](issues/04-azure-openai-resources.md)：另建專題專用的 Foundry，只有立倫使用，課程額度 NTD 2800；已確認 gpt-4.1-mini、gpt-4.1、gpt-4o-mini 支援 structured outputs，gpt-5.6 系列不確定；要部署哪些模型由新 ticket 決定。已由「專題專用 Foundry 要部署哪些模型」更正：額度是 NTD 3000；Microsoft 文件已列出 gpt-5.6 系列支援 structured outputs 與工具呼叫
- [對話狀態存在哪裡](issues/05-conversation-state.md)：交給 Azure Responses API 保存，前端帶 `response_id` 接續；後端不存、不綁使用者、不能回看，Azure 保留 30 天；偏離 §4.2 的地端切換，寫成 ADR 0001（proposed）等組員決定
- [收錄哪些桌遊、存哪些欄位](issues/06-game-coverage-and-fields.md)：15 款（含 Demo 三款）；條件欄位是人數、時長、年齡，偏好欄位是 BGG 的類別、機制、難度；Codex 透過 BGG XML API 產生 repo 外的 JSON，後端匯入指令讀檔寫入
- [Agent 怎麼追問、什麼時候推薦](issues/07-conversation-flow.md)：Agent 依對話規則自己判斷追問或推薦（function calling），程式守三道護欄：人數必填、只推薦工具回傳的桌遊、每則訊息最多呼叫 2 次工具；人數是唯一必要條件，最多推薦 3 款，一律用繁中；查無結果時放寬時長或年齡其中一項，人數不放寬；離題規則也在這張；偏離「程式判斷流程」的取捨寫成 ADR 0002（proposed）
- [標籤詞彙表怎麼定](issues/08-tag-vocabulary.md)：詞彙先從心得歸納，再由立倫審核固定（最多約 30 個），每個標籤有英文代碼、繁中名稱、繁中定義；只描述玩起來的感受，不和條件或 BGG 欄位重複，每個面向只留一個方向；每款的每個標籤有 LLM 給的 0–1 信心分數，給分標準移到心得管線；人工驗證只能刪標籤
- [條件與偏好怎麼比對桌遊](issues/10-matching-strategy.md)：SQL 篩條件；負面偏好優先排後面，再用 RRF 合併結構化分數（標籤信心、類別、機制、難度）與偏好描述對心得摘要的向量相似度，回傳前 3 款；同一個工具再取每款 2 段心得片段當理由出處；embedding 主要為展示 RAG；心得摘要向量放桌遊資料表、心得片段另開一張表，不建索引
- [心得來源走哪條路](issues/16-review-source-decision.md)：心得不用 BGG，由立倫用 Codex 的 goal 模式與 live 網路搜尋，從 PTT、中英文部落格、評測網站收集，提示詞在 `prompts/collect-reviews.md`；每款目標 5 篇、至少 2 篇，逐字擷取感受段落，存進 repo 外的 `reviews.json`；資料庫只存衍生資料，心得片段帶 `source_url`、`site_name`、`language`
- [心得怎麼變成標籤](issues/09-review-to-tags-pipeline.md)：全部寫成後端指令（歸納詞彙表也是，依 §4.2、§7）；每款 1 次 LLM 擷取候選詞、1 次合併成最多 30 個的草稿，立倫編輯 repo 裡的 `tag_vocabulary.json` 走 MR；上標籤每款 1 次、四級給分、門檻 0.5、三項自動檢查，人工驗證用 repo 外的草稿、匯入只允許刪除；心得摘要 120–200 字繁中、和上標籤分開；心得片段依段落切、存原文；每款一個交易、重跑即覆蓋
- [推薦理由要寫什麼、要不要附出處](issues/11-recommendation-reasons.md)：推薦卡片的基本資料與放寬的條件由程式產生，LLM 只寫最多 2 句推薦理由（命中的偏好、心得印證的感受，命中負面偏好要說）並引用心得片段 ID；最終回覆用 structured outputs（`reply` + `recommendations`），service 只認這則訊息的工具結果，無效的丟掉、全部丟掉就換固定文字；出處顯示片段原文、標題、網站並連回原文，英文不翻譯；心得片段資料表加 `title`，不加 `author`。出處的顯示方式已由 ticket 13 更正：只顯示片段原文，不加 `title`
- [需要整合層提供哪些介面](issues/12-integrations-interface.md)：提案在 `integrations-proposal.md`；整合層一次只呼叫 1 次模型，工具迴圈與護欄留在 service；`generate` 不動，新增無狀態的 `generate_json`（批次）和有狀態的 `respond`（對話，只有雲端），embedding 只有 `embed(texts)`；schema 用 strict JSON Schema dict；fake 照腳本回傳並記錄呼叫；雲端用 `openai` SDK、pytest 用 `MockTransport`；`tools` 加 `text.format` 等 Foundry 建好再實測，不行就改用「交卷」工具。embedding 的設定已由「詞彙表改版或換 embedding 模型時怎麼處理」更正：改用 games_advisor 自己的 `GAMES_ADVISOR_EMBEDDING_*`，factory 接收設定值、不讀全域設定
- [API 契約與 prototype 頁面](issues/13-api-contract-and-prototype.md)：`POST /api/v1/advisor/messages` 回 201，請求 `content`、`previous_response_id`，回應 `response_id`、`reply`、`relaxed_constraint`、`recommendations`（`game`、`reason`、`excerpts`）；不串流；三種角色都能用，未登入 401；404 對話過期（前端清空）、503 Azure 連不上（要向組員提議補進 §4.3）；固定文字回舊 id；卡片只顯示心得片段原文、不顯示來源（立倫接受著作權法第 64 條的風險）；參考畫面的按鈕與狀態都列在這張；草圖在 `prototypes/api-contract.html`；這個階段不用 DevUI
- [怎麼驗收推薦結果](issues/14-recommendation-acceptance.md)：pytest（假的 LLM；repository 與匯入指令連 CI 的 PostgreSQL）是合併的唯一標準；真的模型改用「評估題組」檢查（原稱情境題組，避開 §7 的「情境」欄），寫成後端指令在本機真資料上跑，不進 CI、不擋合併，改到對話規則等項目時把分數貼進 MR；10 題對話腳本放 `backend/tests/games_advisor/eval_cases.json`，程式比對工具參數與卡片，人工看 repo 外的報告，分條件分、偏好分、人工項目；只有 3 題 Demo 題要求 3 次全過
- [專題專用 Foundry 要部署哪些模型](issues/17-foundry-model-deployments.md)：對話 gpt-5.6-luna（推理強度 `low`）、心得管線 gpt-5.6-terra（`LLM_BATCH_MODEL`，預設推理強度）、embedding text-embedding-3-large 縮成 1536 維；Japan East、GlobalStandard，部署名稱同模型名稱，TPM 100K／50K／100K；新增 `LLM_REASONING_EFFORT`；逾時對話 30 秒、前端 100 秒、心得管線 300 秒；額度 NTD 3000，預估用約 16%；配額等級、額度是否共用、區域 policy 移到建立 Foundry 的實作 ticket，剩不到 NTD 1,000 時心得管線改用 luna。embedding 的設定名稱已由「詞彙表改版或換 embedding 模型時怎麼處理」更正為 `GAMES_ADVISOR_EMBEDDING_*`
- [詞彙表改版或換 embedding 模型時怎麼處理](issues/18-vocabulary-and-embedding-revisions.md)：同步依代碼比對，刪掉的代碼連帶刪除桌遊上的標籤，新增或改代碼只提醒重標（15 款全部），只改名稱或定義就原地更新；匯入草稿遇到詞彙表沒有的代碼整份拒絕；工具 enum 每則訊息讀資料庫；只在新增桌遊時重新歸納；pytest 檢查評估題組的代碼都在詞彙表；embedding 用 games_advisor 自己的 `GAMES_ADVISOR_EMBEDDING_*`（沒填就是 fake）；每個向量記下產生它的模型，模型不同就當作沒有向量，評估題組指令會拒絕執行；換模型重跑心得摘要與心得片段兩個指令；改維度時再新增 migration
- [LLM 設定也改成 games_advisor 自己的一組嗎](issues/19-games-advisor-llm-settings.md)：不改，LLM 用全域 `LLM_*`，只有 embedding 開例外（換 LLM 不會讓已存資料失效）；factory 照提案讀 settings，批次指令複製 settings 換掉部署、推理強度、逾時；fake 沒給腳本時拋 `LLMUnavailable`，對話 API 回 503；4 個需要 LLM 的指令遇到 `LLM_PROVIDER=fake` 拒絕執行；換 Foundry 後舊對話走 404 清空；實作時要更新 OpenSpec 的 `llm-provider` 規格

## Not yet specified

- 批次指令部署到 Azure 後在哪裡執行；最後整合成一個或多個 Foundry、PostgreSQL 時，games_advisor 的資料怎麼放進部署環境（重跑管線或匯出匯入）；維持多個 Foundry，或其他 domain 要不同的 LLM 模型、推理強度時，games_advisor 的 LLM 改用自己的欄位。

## Out of scope

- 正式頁面：由永傑依交接說明製作（AGENTS.md §5.4）。
- 推薦時不考慮店家有沒有這款桌遊。
- 地端 LLM：AGENTS.md 列為加分項目，之後再做。
- 語音對話。
