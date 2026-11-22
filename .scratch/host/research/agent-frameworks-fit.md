# 三個 Agent 框架怎麼接 Qwen、怎麼展示

## 三行結論

1. 三者都有接 Qwen 文字模型的途徑，但本次查不到三者可直接接 Qwen-Audio-3.1-Realtime 的官方音訊轉接器，文字整合與即時語音要分開看。[Q1][Q2][L1][M1]
2. 三者都有狀態與流程展示手段，LangChain 的 Agent 底層使用 LangGraph，Microsoft Agent Framework 也能在本機畫圖、開 DevUI，不必先用 Foundry。[L2][L3][M2][M3]
3. 現有 LLM 介面不能直接當成即時語音介面，工具迴圈歸誰控制、主持步驟如何對應遊戲階段，都還要由後續 ticket 決定，本報告不做選型。[R1][R2]

查核日期：2026-11-19。以下每個來源代號都連到一手來源，版本與文件日期集中列在文末。未標更新日的網頁，明列為「滾動文件、未標日期」，不以查核日冒充發布日。證據層級是文件、發行中繼資料與現有原始碼的靜態閱讀，未安裝、匯入或執行任何框架，也未呼叫模型 API。

## 1. 能不能接 Qwen 文字模型

| 框架 | 查到的接法 | 套件與維護狀況 |
|---|---|---|
| LangChain | 官方文件列出 `langchain_qwq.ChatQwen`，支援文字、工具呼叫與結構化輸出。也能透過 `ChatOpenAI(base_url=...)` 使用相容的標準文字欄位，但官方提醒它不保留第三方的 `reasoning_content` 等擴充欄位。[L1][L15][Q1] | `langchain-qwq` 0.4.0，2026-10-27 發布。它是社群作者維護、被官方文件收錄的套件，不是阿里雲官方 SDK。發布紀錄列出模型退役後的遷移與工具參數修正，這是維護活動的證據，不代表維護保證。[P3] |
| LangGraph | 節點可以是一般 Python 函式，圖本身不限定模型供應商。可在節點使用前述 `ChatQwen`，也可讓節點呼叫專案自己的 LLM 介面，後者是可行的設計方式，尚未實作。[L4][P2][R1] | LangGraph 本身沒有一個必裝的 Qwen 專用套件。若選 `ChatQwen` 路線，就沿用同一個社群套件與版本。[P2][P3] |
| Microsoft Agent Framework | 官方 `OpenAIChatCompletionClient` 支援自訂 `base_url`，阿里雲文字端點提供 Chat Completions 相容格式，兩份文件合看可形成接法。這是介面相容性的推論，未取得本專案的實際連線證據。[M1][Q1] | 核心 `agent-framework-core` 1.26.0，OpenAI 轉接套件 `agent-framework-openai` 1.18.2，皆於 2026-11-12 發布，由 Microsoft 發布。沒有查到專屬 Qwen 的官方套件或官方 Qwen 端到端範例。[P5][P6] |

`ChatOpenAI` 路線的套件是 `langchain-openai` 1.8.3，官方發布資料顯示 2026-11-19 UTC 更新，搜尋工具讀到的 PyPI HTML 還停在 1.8.2，因此此處採 PyPI JSON 的即時資料。[P4] 三者的接法都不代表每款 Qwen 都支援相同的工具、JSON Schema 或推理參數，仍需按模型與端點驗證。[P3][Q1]

## 2. 能不能接即時語音，框架放在哪一段

阿里雲把 Qwen-Audio-Realtime 列為獨立的 Realtime API。WebSocket 文件明確寫出工具流程：模型提出 function call，由用戶端執行，再送回 `function_call_output` 與 `response.create`。這條流程可以把後端框架接進來，無須先把音訊改走文字模型。[Q2]

| 框架 | 內建支援查核 | 對本案可成立的接法，尚未試跑 |
|---|---|---|
| LangChain | `ChatQwen` 文件的 Audio input 是不支援，官方語音教學示範 STT → LangChain → TTS，並非 Qwen 原生即時語音連線。查不到 Qwen-Audio-3.1-Realtime 專用轉接器。[L1][L5] | Qwen 負責音訊，後端收到工具請求後，由 LangChain 負責文字／工具處理，再回傳精簡結果。若工具查詢不需第二個文字模型，不必為了用框架而多呼叫一個模型，具體怎麼組成 Agent 仍待原型驗證。[Q2][L2] |
| LangGraph | 核心是一般節點與流程控制，查不到內建 Qwen 音訊 session 管理器。官方文件中的語音示範，也不能當作 LangGraph 核心自帶音訊傳輸的證據。[L4][L5] | 讓 Qwen 的工具事件啟動一張圖，例如「檢查權限 → 查局況／規則 → 整理來源 → 回傳」。圖可以只跑確定的函式，也可以在其中呼叫文字模型，兩者是不同設計。[L4][Q2] |
| Microsoft Agent Framework | 查不到核心可直接管理 Qwen 即時音訊的官方 client。Microsoft 的 Voice Live 文件提供「語音服務＋託管 Agent」整合，這需要另外的 Azure 服務與部署，不能等同本機框架直接接 Qwen。[M4][M1] | Qwen 的工具請求交給 Workflow executor 或 Agent 處理，音訊連線留在語音轉接層，也能另接 Microsoft 的語音服務，但那是另一條部署路線。[M5][Q2][M4] |

這些接法是依官方介面提出的整合方式，沒有證據可宣稱已支援所有 Qwen 事件、插話、斷線重連或音訊格式。現階段也不能把「查不到現成音訊轉接器」寫成「三者都接不上」。

## 3. 怎麼記住這一局走到哪個階段

| 框架 | 定義與保存狀態 | 暫停與接續 |
|---|---|---|
| LangChain | 擴充 `AgentState`，透過 `state_schema` 定義自訂欄位。`checkpointer` 按 `thread_id` 保存每段對話的狀態，能用記憶體或資料庫。[L6] | 可用 `HumanInTheLoopMiddleware` 暫停工具，再用 LangGraph 的續跑機制處理人工決定，不必另換成另一套記憶功能。[L7] |
| LangGraph | 用 `TypedDict` 或 dataclass 定義 state，節點回傳更新，邊決定下一步。Checkpointer 保存圖狀態，store 處理跨 thread 的資料。[L4][L8] | `interrupt()` 暫停，使用同一個 `thread_id` 與 `Command(resume=...)` 接續。記憶體 saver 重啟就遺失，SQLite／PostgreSQL saver 可保存到磁碟或資料庫。[L9][L10] |
| Microsoft Agent Framework | Workflow 的 `ctx.set_state()`／`get_state()` 共用資料，executor 可保存自己的狀態。Checkpoint 包含 executor、待處理訊息、請求與共用狀態。[M6][M7] | 可用 `checkpoint_id` 恢復。內建有記憶體、檔案與另裝套件的 Cosmos DB storage，檔案方案能跨程式重啟，記憶體方案不能。[M7] |

對 host 的設計含義：可以定義 `match_id`、`observed_game_phase`、`host_step`、`source_ids` 等欄位，但這只是示例，不是契約。地圖已限定首版唯讀，所以框架記住的「主持目前在查規則」與 `matches` 記錄的遊戲階段應分開，不能讓模型一句話就覆寫玩家填的局況。[R2]

框架 checkpoint 保存的是框架狀態，不等於保存 Qwen 的音訊上下文。Qwen 官方目前列 50 段音訊往返、累積 300 秒的歷史容量，超過會丟棄較早歷史，這也不是「每 300 秒必須重連」的意思。重連時怎麼把階段與摘要補回去，仍需語音連線 ticket 設計。[Q3]

## 4. 怎麼展示流程圖與查詢過程

| 框架 | 本機就能看、不需觀測服務帳號 | 選用服務與費用 |
|---|---|---|
| LangChain | Agent 底層是 compiled graph，可用 `get_graph().draw_mermaid()` 輸出圖。`stream()` 的 `updates` 能看到模型步驟與工具結果，也能送出自訂進度，要成為漂亮的展示畫面，仍要自己呈現這些事件。[L2][L3][L11] | LangSmith 提供 trace 與 Studio。它是另一個服務介面，本機 Server 可供 Studio 連線，官方也允許關閉 tracing。雲端帳號有免費額度，超額與付費方案另計。[L12][L13] |
| LangGraph | 同樣能輸出 Mermaid，另可讀取 state 與歷史 checkpoint，搭配節點更新展示「走到哪一步、工具得到什麼」。Mermaid 文字可以完全在本機產生，不要把預設 PNG 渲染方式誤認成一定離線。[L3][L10] | 同樣可選 LangSmith Studio，互動畫面能看走過的節點、中間狀態與 trace，不能因此說 LangGraph 必須註冊 LangSmith 才能展示。[L12] |
| Microsoft Agent Framework | `WorkflowViz.to_mermaid()`／`to_digraph()` 不需額外依賴。圖片輸出才需 `graphviz` Python 套件與 Graphviz 系統程式，DevUI 可在 loopback 開網頁並看 OpenTelemetry trace，不需要 Foundry 帳號。[M2][M3] | DevUI 是開發用 sample，套件仍是預覽版，Foundry 是選用的雲端部署與觀測路線，需 Azure 資源。本次沒有取得適用本案的完整 Foundry 費率，不能填成免費。[P7][M3][M4] |

LangSmith 價格頁在查核時列 Developer 每席每月 US$0，含每月 5,000 筆 base traces、超額計費，Plus 每席每月 US$39，另有用量費。模型 API 費用仍另外計算，註冊免費方案也不等於所有展示方式無上限免費。[L13]

展示上的共同限制是：流程圖只顯示設計出的節點，不能自動解釋遊戲階段，trace 也不會自動變成每筆 SQL 與規則引用的完整證據。若展示要看「查了哪些來源」，工具結果需明確回傳來源識別與摘要，再由畫面顯示，這是本案需補的事件資料設計。[L11][M3][R2]

## 5. 和本專案規則、現有介面合不合

### 5.1 專案現況，唯讀原始碼

`backend/pyproject.toml` 的 `requires-python` 是 `>=3.13`，目前宣告 `openai>=3.49.0`、FastAPI、SQLAlchemy、`psycopg[binary]` 等，沒有三個框架的套件。這是宣告內容，未查安裝環境或執行相依套件解析。[R3]

`LLMProvider` 有同步的 `generate()`、`generate_json()`、`respond()`。類別契約寫明「每個方法只呼叫模型 1 次」，工具迴圈與上限在 service，`CloudLLMProvider` 呼叫 Azure OpenAI Responses API，以 `previous_response_id` 接續。介面沒有音訊串流、取消播放或 WebSocket session。[R1][R6]

`FakeLLMProvider` 是手寫腳本式 fake，記錄 `calls`，依序回傳 `FakeResponse` 或例外，腳本耗盡會失敗。factory 現在只支援 `fake`、`cloud`，`local` 明確未實作，沒有 Qwen provider。[R7][R8]

### 5.2 同步資料庫，不等於所有程式都禁止 async

| 框架 | 查核結果與專案影響 |
|---|---|
| LangChain | 有同步 `invoke()`、`stream()`，也有非同步版本，不強制把 repository 換成 async。[L2][L11] |
| LangGraph | 有同步節點與 `graph.invoke()`，PostgreSQL checkpointer 也分同步 `PostgresSaver` 與 `AsyncPostgresSaver`，可選同步路線。[L4][L10] |
| Microsoft Agent Framework | Python 官方 Agent／Workflow 執行介面回傳 awaitable 或非同步事件串流，需非同步呼叫方式，工具可用一般 `def`，不等於強迫 SQLAlchemy 使用 async。[M5][M8][M9] |

依專案規則做整合時，資料庫仍由同步 service／repository 存取，若有非同步語音或 Workflow，不應把同步查詢直接塞進音訊事件迴圈，也不應跨執行緒共用 session。這是分層與資源生命週期的設計要求，未做併發測試。框架 saver 自動建表也不能直接取代本專案 Alembic 與 migration 審核流程。[R4][L10]

### 5.3 手寫 fake

LangChain 官方文件有 `GenericFakeChatModel`、`FakeListChatModel`，可供 LangChain 與使用其模型介面的 LangGraph 參考。前者可腳本化工具請求，但沒有實作 `bind_tools`，官方範例以子類別補上，後者會循環回覆，行為和本專案「腳本耗盡就失敗」不同，不宜直接視為等價替身。[L14][R7]

Microsoft 官方 Python 文件有不呼叫模型的 `EchoAgent` 與自訂 `BaseAgent` 範例，可參考替換介面的方式，本次查不到公開、可直接使用的官方 Python `FakeChatClient` 套件類別。這是查不到，不是斷言沒有。專案仍可依介面手寫 `Fake...`，不需引入 mock 套件。[M8][R4]

### 5.4 分層與目前不能直接套用的地方

三者都能包在專案分層內，但需分開放：模型廠商 client 與音訊轉接屬於 `integrations/`，知道「這款遊戲目前在哪個階段」的規則與流程屬於 `host.service`，查規則應呼叫 `rules_qa.service`，不能讓 integrations 反過來知道 domain。[R4]

目前有兩個待決問題，不能用換端點掩蓋：

- 現有 `respond()` 的 Azure 雲端對話 ID、strict JSON 與單次模型呼叫契約，不能由「Qwen 相容 Chat Completions」推成完整相容，即時音訊更需要另外的串流生命週期介面。[R1][Q1][Q2]
- `create_agent` 與 Microsoft Agent 會管理模型／工具迴圈，若整包藏進一次 `respond()`，就和目前「service 管工具迴圈」的契約不同。LangGraph 可以只編排一次工具處理，採哪種粒度、要不要變更契約，留給決策 ticket。[R1][L2][M9][L4]

## 6. 套件、授權、Python 3.13 與穩定度

| 項目 | LangChain | LangGraph | Microsoft Agent Framework |
|---|---|---|---|
| 核心版本 | `langchain` 1.5.2，2026-11-18 發布。[P1] | `langgraph` 1.2.22，2026-11-14 發布。[P2] | `agent-framework-core`／`agent-framework` 1.26.0，2026-11-12 發布。[P5] |
| Python | `>=3.11,<4`，列出 3.13。[P1] | `>=3.10`，列出 3.13。[P2] | `>=3.11`，列出 3.13。[P5] |
| 穩定度 | PyPI 標 Production/Stable。[P1] | PyPI 標 Production/Stable。[P2] | 核心標 Production/Stable，DevUI 1.0.0b261112 仍為預覽版，不可一概說全部正式。[P5][P7] |
| 授權 | 核心 MIT。[P1] | 核心 MIT。[P2] | 核心 MIT。[P5] |

這些 Python 條件包含本案 3.13，但不是「已在本專案安裝成功」或「現有 lockfile 可直接解析」的證明。

會增加的套件依接法而不同，以下是發布 metadata 可確認的主要組成，完整遞迴依賴仍以各來源的 `requires_dist` 為準，本次未產生 lockfile：

- LangChain 核心直接依賴 `langchain-core`、`langgraph`、Pydantic，若採 `ChatQwen`，另加 `langchain-qwq`，它又依賴 `langchain-openai`、`json-repair`、`requests`、`orjson` 等。`langchain-core` 本身依賴 `langsmith` SDK，但安裝 SDK 不等於必須開啟雲端 tracing。[P1][P3][P8][L12]
- LangGraph 直接依賴 `langchain-core`、`langgraph-checkpoint`、`langgraph-prebuilt`、`langgraph-sdk`、Pydantic、`xxhash`。若節點只呼叫專案自己的介面，不必為此另加 Qwen 模型 wrapper，若要持久化 PostgreSQL，另有 `langgraph-checkpoint-postgres` 3.2.1，含 `psycopg-pool` 等依賴。[P2][P9]
- Microsoft 的最小文字接法需留意套件拆分：1.26.0 的 core metadata 本身沒有 `openai` client 依賴，需搭配 `agent-framework-openai` 1.18.2，core 有 `msgspec`、Pydantic、`python-dotenv`、`opentelemetry-api`、PyYAML 等。`agent-framework` 主套件其實指定 `core[all]`，會連許多非必要連接器一起裝，部分仍是預覽版。展示若用 DevUI，再加其套件與 `opentelemetry-sdk`、FastAPI、Uvicorn，圖片匯出另需 Graphviz。[P5][P6][P7][M2]

相依條件的靜態對照：`langchain-openai` 1.8.3 要求 `openai>=2.45.0`，Microsoft OpenAI adapter 要求 `openai>=2.25.0,<4`，和本專案 `>=3.49.0` 有交集。DevUI 要求 `fastapi>=0.115.0,<0.163.0`，和本專案 `>=0.162.0` 也有交集，這只能排除這兩項「範圍完全不相交」的問題，不能保證整份依賴相容。[P4][P6][P7][R3]

## 三欄比較：展示重點是階段與查詢過程

以下優缺點是依前述機制做的本案分析，不是效能實測或框架排名。

| LangChain | LangGraph | Microsoft Agent Framework |
|---|---|---|
| 有現成 Agent 與 Qwen 文字 wrapper，能快速把工具名稱、輸入與結果接成展示事件。[L1][L11] | 可把主持步驟直接建成明確節點，流程圖與實際執行路徑較容易對照。[L3][L4] | 本機 WorkflowViz、DevUI 與 trace 都有官方文件，不必改成 .NET 或先搬 Foundry。[M2][M3] |
| 預設 Agent 的「模型→工具→模型」不會自然長成遊戲階段，仍需自訂狀態與呈現，既有 service 工具迴圈也要協調。[L2][L6][R1] | 要自行定義 state、節點、邊、儲存與展示，框架本身沒有替本案決定遊戲階段。[L4][L10] | Python 執行採非同步形式，需接好同步資料庫邊界，DevUI 預覽版與正式產品畫面也要分開。[M5][P7][R4] |
| 可本機輸出圖與事件，選用 LangSmith 才增加服務帳號與可能用量費。[L3][L12][L13] | 同樣可本機輸出圖與狀態，精確的「查了哪些來源」仍取決於工具回傳資料。[L10][L11] | Mermaid／DOT 文字輸出無額外依賴，圖像匯出、雲端觀測與部署各有額外條件。[M2][M3][M4] |

## 查不到的項目

- 三者針對 Qwen-Audio-3.1-Realtime 的官方現成音訊轉接器與端到端範例。查過 LangChain Qwen 整合、語音教學、LangGraph 文件，以及 Microsoft provider／語音文件，不能以文字模型相容性代替音訊支援證據。[L1][L5][M1][M4]
- Microsoft 官方 Python 可公開使用的 `FakeChatClient` 類別。查過官方自訂 Agent 文件、Microsoft Learn 與官方 repo 的搜尋結果，僅取得非模型 EchoAgent 參考。GitHub repo tree API 查詢回 404，沒有據此推測測試原始碼內容。[M8]
- 本專案的實際安裝相容性、Qwen 工具正確率、執行延遲、暫停恢復與 UI 效果。本次被明確限制不能安裝或試跑，所以這些都是待驗證。
- 原報告的週下載量 1,439 萬與 4.2 萬：官方 PyPI 發布 metadata 沒有這個欄位，原報告引用的 PyPI Stats 不符合本次一手來源範圍，未重述為已核實數字。「學習成本最高」「社群最小」也沒有可重現的官方比較基準。
- 適用本案的完整 Foundry 帳單與 Studio 是否可完全不登入使用。官方 Studio 文件顯示透過 LangSmith 網頁連本機 Server，沒有給足「完全免帳號」的保證，本機 Mermaid／事件輸出則不需這個服務。[L12][M4]

## 和選型查核報告不一致的地方

對照的是 2026-11-16 HTML 報告第 02 節，只核對本次指定的三個框架，不沿用其選型排序。

| 原報告的項目 | 本次核對 |
|---|---|
| 三套方案的比較集合 | 原表沒有 LangChain，不能直接當成本次三選一的完整比較。本文補上 LangChain，未擴充候選。[R5] |
| LangGraph 1.2.22、Microsoft 1.26.0、核心 MIT | 這兩個版本與授權仍吻合，本次新增 LangChain 1.5.2。[P1][P2][P5] |
| LangGraph 18.8%、Microsoft 調查未列出 | 官方 2026 調查 v2026.1，該題 4,400 人，LangGraph 825 人、18.8%，吻合，LangChain 是 1,329 人、30.2%，Microsoft Agent Framework 未單列。這是受訪者使用比例，不是市場占有率。[S1] |
| 週下載量與「社群最小」 | 本次查不到可採用的一手證據，不以下載量推成社群規模，見前節。 |
| LangGraph 沒有內建語音，要自行接 Realtime | 在本次查到的核心與音訊文件範圍內沒有矛盾，但要補上：官方已有語音教學，屬 STT／Agent／TTS 組裝，不是 Qwen 原生 S2S 轉接器。[L5] |
| Microsoft 走 Voice Live／GPT-Live | 這些是 Azure 語音服務路線，不是框架唯一用法。框架可本機執行，也能走相容文字端點，因此不能推成「只有搬 Foundry／改 .NET 才能用」。[M1][M3][M4] |
| Microsoft Python 部分功能預覽 | 要精確到套件：核心已正式，DevUI 等仍預覽，整句只寫預覽容易讓人誤以為核心也未正式。[P5][P7] |
| 首版不使用框架與原報告排序 | 是原報告的設計判斷，地圖現已明訂展示必須用三者之一，這個前提不同。本文不沿用排序，也不替立倫決定。[R2][R5] |
| 暫停續跑、人工審核、觀測另計費 | 能力可由官方 checkpoint／interrupt／Workflow 文件佐證，但觀測不是全部都要付費：本機圖、事件、DevUI 可用，LangSmith 也有有限額的免費方案。[L7][L9][M7][L13][M3] |

## 一手來源與版本紀錄

本節所有來源均於 **2026-11-19 查核**。PyPI 版本日期採發布時間的 UTC 日期，官方網站若沒有顯示或提供更新日期，直接記「未標日期」。文件是當日取得的滾動版，沒有假定與某個 release tag 完全一致。

| 代號 | 版本或文件日期 |
|---|---|
| P1 | `langchain` 1.5.2，2026-11-18，Python、MIT、依賴與 Stable classifier。[PyPI JSON][P1] |
| P2 | `langgraph` 1.2.22，2026-11-14，Python、MIT、依賴與 Stable classifier。[PyPI JSON][P2] |
| P3 | `langchain-qwq` 0.4.0，2026-10-27，套件維護者、MIT 與遷移說明。[PyPI][P3] |
| P4 | `langchain-openai` 1.8.3，2026-11-19，即時 JSON 比搜尋取得的 1.8.2 HTML 新。[PyPI JSON][P4] |
| P5 | `agent-framework`／core 1.26.0，2026-11-12。[core JSON][P5]、[主套件 JSON](https://pypi.org/pypi/agent-framework/1.26.0/json) |
| P6 | `agent-framework-openai` 1.18.2，2026-11-12。[PyPI JSON][P6] |
| P7 | `agent-framework-devui` 1.0.0b261112，2026-11-12。[PyPI JSON][P7] |
| P8 | `langchain-core` 1.8.3，2026-11-18。[PyPI JSON][P8] |
| P9 | `langgraph-checkpoint-postgres` 3.2.1，2026-11-14。[PyPI JSON][P9] |
| Q1 | 阿里雲 OpenAI compatible — Chat，頁面更新 2026-11-16。[官方文件][Q1] |
| Q2 | Qwen-Audio-Realtime WebSocket access，更新 2026-11-16，列出 3.1 Plus／Flash。[官方文件][Q2] |
| Q3 | Qwen-Audio realtime voice conversation，滾動文件、未標日期，明列 3.1 Plus／Flash。[官方文件][Q3] |
| L1–L15 | LangChain／LangGraph 當日滾動文件，未標更新日期，具體 API 與限制見各引用頁。核心與轉接套件版本分列 P1–P4、P8–P9。 |
| M1 | OpenAI-Compatible Endpoints，`ms.date` 2026-10-22，`updated_at` 2026-10-28。[官方文件][M1] |
| M2 | Workflow Visualization，`ms.date` 2026-05-27，`updated_at` 2026-08-25。[官方文件][M2] |
| M3 | DevUI，`ms.date` 2026-10-23，`updated_at` 2026-11-18。[官方文件][M3] |
| M4 | Voice Live hosted-agent integration，`ms.date` 2026-05-14，`updated_at` 2026-06-30。[官方文件][M4] |
| M5 | Workflow Builder & Execution，`ms.date` 2026-10-22，`updated_at` 2026-10-28。[官方文件][M5] |
| M6 | Workflow State，`ms.date` 與 `updated_at` 皆為 2026-09-24。[官方文件][M6] |
| M7 | Workflow Checkpoints，`ms.date` 2026-09-16，`updated_at` 2026-11-18。[官方文件][M7] |
| M8 | Custom Agents，`ms.date` 2026-06-01，`updated_at` 2026-08-25。[官方文件][M8] |
| M9 | Function tools，`ms.date` 2026-10-22，`updated_at` 2026-11-18。[官方文件][M9] |
| S1 | Stack Overflow Developer Survey 2026，資料版本 v2026.1。[官方資料][S1] |
| R1–R4、R6–R8 | 本 worktree 當日原始碼／規則快照，版本為 backend 0.1.0、AGENTS 1.11（2026-11-17），未以其他 worktree 或記憶代替。 |
| R5 | repo 外的選型查核報告，文件自載查核日 2026-11-16，僅作本次待核對輸入。 |

[P1]: https://pypi.org/pypi/langchain/1.5.2/json
[P2]: https://pypi.org/pypi/langgraph/1.2.22/json
[P3]: https://pypi.org/project/langchain-qwq/0.4.0/
[P4]: https://pypi.org/pypi/langchain-openai/1.8.3/json
[P5]: https://pypi.org/pypi/agent-framework-core/1.26.0/json
[P6]: https://pypi.org/pypi/agent-framework-openai/1.18.2/json
[P7]: https://pypi.org/pypi/agent-framework-devui/1.0.0b261112/json
[P8]: https://pypi.org/pypi/langchain-core/1.8.3/json
[P9]: https://pypi.org/pypi/langgraph-checkpoint-postgres/3.2.1/json
[Q1]: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
[Q2]: https://www.alibabacloud.com/help/en/model-studio/audio-realtime-websocket-access
[Q3]: https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-audio-realtime-user-guides
[L1]: https://docs.langchain.com/oss/python/integrations/chat/qwen
[L2]: https://docs.langchain.com/oss/python/langchain/overview
[L3]: https://docs.langchain.com/oss/python/langgraph/graph-api-visualize
[L4]: https://docs.langchain.com/oss/python/langgraph/use-graph-api
[L5]: https://docs.langchain.com/oss/python/langchain/voice-agent
[L6]: https://docs.langchain.com/oss/python/langchain/short-term-memory
[L7]: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
[L8]: https://docs.langchain.com/oss/python/langgraph/persistence
[L9]: https://docs.langchain.com/oss/python/langgraph/interrupts
[L10]: https://docs.langchain.com/oss/python/langgraph/checkpointers
[L11]: https://docs.langchain.com/oss/python/langchain/streaming
[L12]: https://docs.langchain.com/langsmith/quick-start-studio
[L13]: https://www.langchain.com/pricing
[L14]: https://docs.langchain.com/oss/python/langchain/test/unit-testing
[L15]: https://docs.langchain.com/oss/python/integrations/chat/openai
[M1]: https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting/openai-endpoints
[M2]: https://learn.microsoft.com/en-us/agent-framework/workflows/visualization
[M3]: https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/devui/
[M4]: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-voice-live-hosted-agent-integration
[M5]: https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/builder-and-execution?pivots=programming-language-python
[M6]: https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/state
[M7]: https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
[M8]: https://learn.microsoft.com/en-us/agent-framework/concepts/agents/custom-agents
[M9]: https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools
[S1]: https://survey.stackoverflow.co/2026/ai/data/ai-orch
[R1]: ../../../backend/app/integrations/llm/base.py
[R2]: ../map.md
[R3]: ../../../backend/pyproject.toml
[R4]: ../../../AGENTS.md
[R5]: /Users/user/Desktop/團隊專題/02_選題研究/AI語音主持選型查核報告.html

[R6]: ../../../backend/app/integrations/llm/cloud.py
[R7]: ../../../backend/app/integrations/llm/fake.py
[R8]: ../../../backend/app/integrations/llm/factory.py
