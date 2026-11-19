# AI 語音主持

## Destination

一份 `.scratch/host/spec.md`，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格，並拆成 TDD 實作 ticket（放 `.scratch/host-impl/issues/`）。
範圍：主持人在《血與刃的白薔薇》的一局裡帶流程、回答規則問題；即時語音模型與 Agent 框架的選擇（先用真的聲音小測過才寫進 spec）；後端 API 契約；參考畫面與交接說明。

## Notes

- Domain：`host`（#3 AI 遊戲主持，立倫主責，優先級「應做」）。後端會在 `backend/app/domains/host/`；前端只做 `data/`、`state/`、`prototypes/` 與交接說明（AGENTS.md §5.4）。2026-11-19 畫地圖時 repo 裡還沒有任何 host 的程式。
- 規則：遵守 `AGENTS.md`（AI 只讀，不得修改）。術語用 AGENTS.md §10 與 `GLOSSARY.md` 的提案區。不得修改 `openspec/`。
- Skills：`grilling` ticket 呼叫 grilling 與 domain-modeling；`research` ticket 呼叫 research；`prototype` ticket 呼叫 prototype。
- Ticket 的 `Status:` 用 `open`、`claimed`、`resolved`。
- 分支：`feature/host`（2026-11-19 立倫決定，原名 `docs/host-wayfinder`）。地圖、決策 ticket、spec、實作 ticket 與之後的程式都放這一個分支，開同一支 PR。這和 games_advisor「先開文件 MR、再一張 ticket 一個 MR」的做法不同。
- 這張地圖只做決策，不寫 `backend/`、`frontend/`、`device/` 的程式。原型放 `.scratch/host/prototypes/`，research 結果放 `.scratch/host/research/<name>.md`。
- 附件（repo 外）：
  - 選型查核報告：`/Users/user/Desktop/團隊專題/02_選題研究/AI語音主持選型查核報告.html`。**它是輸入，不是定案**：沒做桌邊實測與中文盲聽，報告自己也寫只供選型討論。引用它的數字前要回查一手來源。
  - mattpocock 流程指南：`/Users/user/Desktop/團隊專題/99_其他/mattpocock-skills_開發指南.md`（§0、§1 是立倫的專案做法）。
- 和 wayfinder 原版不同的做法：
  - `research` ticket 不需要立倫在場。由持有地圖的 wayfinder session 自己用 Orca 派 research worker（`orca orchestration worker-start`），worker 回報給它，不回報給總管（2026-11-19 立倫決定）。它驗收後更新地圖：把結論寫進 Decisions so far，把變清楚的問題開成新 ticket。全部結案後，向總管回報一次摘要。不開 `research/<name>` 分支、不開 subagent、不 push。research worker 不得再往下派工。
  - 派 research 的規定：
    - 一個 worker 一張 ticket。
    - worker 只能改自己的 ticket 檔與自己的結果檔，不改 `map.md`，不 commit。
    - 只用一手來源，每項附連結與查核日期。查不到就寫「查不到」，不用模型的記憶補。
    - 規則書這類有著作權的內容，只能用自己的話摘要。
  - 派 research 用的模型：收集網路資料用 Codex（2026-11-19 時只有 `gpt-6.1-sol` 派得動）；要讀本機資料庫或程式的用 Claude `opus` 以上。不要用 Claude `sonnet` 派需要跑指令或改檔的工作，它每個動作都會跳權限提示給立倫。`--effort` 一定要和 `--model` 一起給。
  - 驗收 research（不合格就用 `orca orchestration send` 退回原 worker，不自己代修）：
    - 只動了那兩個檔。
    - 來源確實是一手的。
    - 沒有貼原文。規則書要用資料庫全文比對。
    - 「查不到」與「要問立倫」是讀完整份資料後才下的結論。
  - `grilling`、`prototype` ticket 要立倫在場，一次一張。
- 畫地圖時定下的範圍與方向（2026-11-19，立倫）：
  - 需求前提：反應快、感情豐富的中文、口音不限、能查資料。
  - 主持人以帶流程為主，也回答規則問題。規則問題用 `rules_qa`（永傑主責）已有的規則檢索，不另建規則庫。
  - 首版只做一款：《血與刃的白薔薇》（Blades & Rose，BGG 編號 400566）。`matches` 已有它的回合紀錄格式與陣營（`backend/app/domains/matches/game_definitions.py`），`rules_qa` 已有它的規則影片。
  - 聲音從桌上的手機或平板進出：開 Flutter Web 頁面，用它的麥克風與喇叭。
  - 首版主持人只讀資料，不幫忙記回合。回合照舊由玩家在戰績畫面輸入。
  - 模型首選方向（不是定案）：阿里雲的 `Qwen-Audio-3.1-Realtime`。Flash 或 Plus、要不要把難題轉交後端的文字思考模型，由決策 ticket 決定。Azure 的 `gpt-realtime-2.1` 只當備案，不排實測。
  - 為了展示，一定要用 Agent 框架，三選一：LangChain、LangGraph、Microsoft Agent Framework。展示重點是「看得到主持人走到哪個階段、查了什麼資料」。三個都接不上時回來問立倫，不自行改成不用框架。
  - 阿里雲帳號由立倫自己開、用自己的額度，金鑰只放本機 `.env`。測試只用組員自己的聲音。
- 會碰到的規則（決策時要對照）：
  - AGENTS.md §4.2：domain 不得直接 import 模型廠商的 SDK，外部服務一律包在 `integrations/` 後面；domain 之間只能呼叫對方的 `service`。
  - AGENTS.md §2 第 4 點：新增第三方套件要在 MR 說明寫理由。
  - AGENTS.md §3：`integrations/llm/` 由瑋鋐擁有，`integrations/tts/` 由永傑擁有（2026-11-19 時還不存在）。改共用區要 @ 擁有者。
  - AGENTS.md §5.3：前端不放任何秘密；只能在網頁上用的程式碼要包在 `core/platform/` 的介面後面。
  - AGENTS.md §7.5：domain 的測試一律用手寫 fake，不連真正的外部服務。
- 固定偏好：
  - 不問時程問題，推薦答案也不附日期或天數。
  - commit、PR、文件都不加 AI 署名。
  - 不 push、不建 GitHub issue、不開 research 分支。
  - 抓取的資料、規則書原文、錄音檔都不進 repo。規則流程只能用自己的話摘要。
  - 立倫和組員各用自己的 LLM、embedding 模型與 PostgreSQL；設定不要假設共用。

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

（還沒有結案的 ticket）

## Not yet specified

<!-- in-scope fog you can't ticket yet; graduates as the frontier advances -->

- 主持人的人設與說話風格：開場、宣布結果、緊張時刻各用什麼語氣，寫成給模型的指令。等「用真的聲音試聽 Qwen 主持人」與「主持人在一局裡怎麼帶流程」有結果才問得清楚。
- 整合層介面與 fake：即時語音與框架的程式放在 `integrations/` 的哪個資料夾、由誰擁有、fake 長什麼樣。用 Qwen 與框架偏離 §4.2「LLM 一律透過 `integrations/llm` 的介面」時，要不要寫 ADR 並請組員同意。等模型、框架、連線方式三張決策 ticket 結案。
- 主持要不要存資料：要不要有自己的資料表（例如每場主持的紀錄），對話內容存不存、存多久。
- 一局超過模型連線上限時怎麼接續（選型報告寫 Qwen 只保留 300 秒歷史音訊，待查核）。
- API 契約、參考畫面與交接說明：路徑、請求與回應、錯誤狀態碼、畫面上的按鈕與狀態。
- 怎麼驗收：pytest 用 fake 驗什麼；真的模型要量什麼（首音時間、停播時間、誤停率、中文語氣盲聽）、門檻多少、算不算合併條件。
- 費用上限：一局大約花多少、額度快用完時怎麼辦。
- 聲音送到新加坡這件事，要不要告知組員、寫進哪份文件。
- 寫 `spec.md`，再拆成實作 ticket（最後兩步）。

## Out of scope

<!-- work ruled beyond the destination; closed, never graduates -->

- 接發牌機與睜眼偵測（`dealer`，新善主責）：`device/` 目前只有攝影機與馬達的骨架，沒有連線。之後另開一張地圖。
- 正式頁面：由永傑依交接說明製作（AGENTS.md §5.4）。
- 第二款以上的遊戲。
- 從聲音認出是哪位玩家。
- 地端模型；要求台灣口音。
- 寫 `backend/`、`frontend/`、`device/` 的程式：Destination 只到寫好 spec 並拆成實作 ticket。
