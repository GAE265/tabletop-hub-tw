# 需要整合層提供哪些介面

Type: grilling
Status: resolved
Blocked by: 04, 07, 10
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

列出 games_advisor 需要 `integrations/llm` 與 `integrations/embedding` 提供的介面：函式名稱、輸入、輸出、錯誤情況、fake 實作的行為。

現況：

- `LLMProvider` 只有 `generate(prompt: str) -> str`（`backend/app/integrations/llm/base.py`），不能傳多輪訊息，也不能要求固定格式輸出。
- `integrations/embedding/` 不存在。
- `LLM_PROVIDER=cloud` 尚未實作（`backend/app/integrations/llm/factory.py`）。

產出：一份給瑋鋐（`integrations/` 擁有者）的介面提案。整合層由誰實作，提案時再談；games_advisor 內的程式由立倫寫。

## Answer

2026-11-08 與立倫 grilling 定案（3 輪，最後一輪是和 AGENTS.md 逐條比對）。

**提案全文：[`integrations-proposal.md`](../integrations-proposal.md)**，內容包含介面、型別、錯誤、fake 行為、設定欄位、和 AGENTS.md 的出入，以及給實作者的 §7 情境表格。這裡只列決定與沒有採用的方案。

**1. 整合層一次只呼叫 1 次模型**

- 工具迴圈、「每則訊息最多呼叫 2 次工具」、人數檢查都寫在 `games_advisor` service。第 3 次呼叫時，service 傳 `allow_tool_calls=False`，整合層轉成 `tool_choice: "none"`。
- 整合層固定 `parallel_tool_calls: false`：structured outputs 不相容平行工具呼叫，而且平行呼叫會打亂「先查，0 款才放寬」的順序。
- 沒有採用：把迴圈包在整合層，由 service 傳入工具處理函式。「最多 2 次」是 domain 規則，AGENTS.md §4.2 規定整合層不能知道 domain；而且包起來之後，pytest 很難一步一步驗護欄。

**2. 方法**

- `generate(prompt)` 不動，心得摘要用它。
- `generate_json(instructions, input, schema)`：無狀態（`store=false`），用在擷取候選詞、合併同義詞、上標籤。地端也能實作。
- `respond(instructions, input, tools, output_schema, previous_response_id, allow_tool_calls)`：有狀態（`store=true`），用在推薦 Agent 的對話。只有雲端實作，地端拋 `NotImplementedError`，ADR 0001 說的「切到地端就不能用」直接反映在介面上。
- `integrations/embedding`：只有 `embed(texts) -> vectors` 一個方法。線上傳長度 1 的 list；一個請求送幾段由實作決定；向量長度等於 `EMBEDDING_DIM`；空字串拋 `ValueError`；零向量或維度不符拋 `EmbeddingError`（所有實作共用的檢查，fake 也會檢查）。
- 沒有採用：只開一個萬用的 `respond`，批次也用它。這樣看不出哪些用途可以換地端。

**3. 型別**：`JsonSchema(name, schema)`、`ToolSpec`、`ToolCall`、`ToolResult`、`LLMResponse`（`response_id`、`tool_calls`、`output`、token 用量）。

- schema 一律用 JSON Schema dict，由 domain 寫成符合 Azure strict 的格式（全部欄位 required、`additionalProperties: false`、選填欄位可為 null）。整合層一律送 `strict: true`，不驗證輸出。
- 沒有採用：傳 Pydantic 類別，由整合層轉換。工具參數與上標籤的 enum 要從資料庫動態產生，用 dict 最直接。
- 結果型別不叫 `Turn`：`turn` 是 AGENTS.md §10.2 的「回合」。提案講到對話時，用「每次呼叫」或「每則訊息」，不用「輪」。
- `LLMResponse` 帶 token 用量，讓 service 記 log：課程額度只有 NTD 2800，而且接續對話時前面的輸入 token 會重複計費。

**4. 錯誤**：`LLMError`（基底類別，也用在 401 等設定錯誤）、`LLMUnavailable`、`LLMConversationNotFound`、`LLMOutputRejected`、`EmbeddingError`（基底類別）、`EmbeddingUnavailable`。都不繼承 `core.errors.AppError`，HTTP 狀態碼由 service 轉換。

- 線上的「查桌遊」轉 `preference_text` 失敗時，整則訊息直接失敗，不降級成只用結構化分數排序。

**5. Fake**

- `FakeLLMProvider(reply, json_outputs, responses)`：照腳本依序回傳，腳本項目是例外時就拋出；`response_id` 由 fake 依序產生，收到不是自己產生過的 `previous_response_id` 就拋 `LLMConversationNotFound`；每次呼叫都記在 `fake.calls`；不檢查 schema 與 `allow_tool_calls`；腳本用完時拋 `AssertionError`。
- `FakeEmbeddingProvider(dim, vectors, error)`：可以指定某段文字的向量，沒指定的用 sha256 產生固定的單位向量；`dim` 從設定讀。

**6. 設定與套件**

- `LLM_ENDPOINT`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`（預設 60）；`EMBEDDING_PROVIDER`、`EMBEDDING_ENDPOINT`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`。每個 provider 只綁一個部署；需要時再加 `LLM_BATCH_MODEL`。
- 雲端實作用 `openai` SDK，只在 `integrations/*/cloud.py` 裡 import。
- 雲端實作的 pytest 用 httpx `MockTransport` 假造 Azure 的回應。沒有採用「打真的 Azure，沒金鑰就 skip」：CI 拿不到金鑰（§2.1），也不能用 skip 蓋掉失敗（§7.2）。

**7. 延後：在 Azure 實際驗證 `tools` 加 `text.format`**

- 立倫決定等專題專用的 Foundry 建好再測，不用既有的資源。列成第一張實作 ticket，一起驗證 v1 端點、`tool_choice: "none"`、過期 id 和內容過濾的實際回應（提案第 10 節）。
- 備案：不能一起用時，最終輸出改由「交卷」工具 `submit_recommendations` 帶出，`respond` 的 `output_schema` 改成可以不帶。

**8. 和 AGENTS.md 的出入**（提案第 9 節）

- §4.2：`respond` 只有雲端實作（ADR 0001、0002，proposed）。如果組員否決 ADR 0001，`respond` 就改成每次傳完整的訊息紀錄。
- §4.2「embedding 同理」：另外開 `EMBEDDING_PROVIDER` 是我們的解讀，待瑋鋐確認。
- §7.5：實作 `cloud` 後要改 2 個既有測試（參數改成 `local`），在 MR 寫理由、經審核者同意。
- §4.3：對話 API 的 5xx 不在清單裡，交給「API 契約與 prototype 頁面」。

術語：`GLOSSARY.md` 沒有變動，新名詞都是實作型別，不是領域術語。不新增 ADR：這些決定都可以再改，不符合「難以回頭」的條件。

**留給其他 ticket 的事**

- 「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」：每種例外對應的 HTTP 狀態碼與錯誤碼；失敗時回傳哪個 `response_id`。
- 「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」：設定欄位的值、要不要 `LLM_BATCH_MODEL`、批次的逾時。
- 「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」：換模型時改 `EMBEDDING_MODEL`、`EMBEDDING_DIM`。
- 「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」：真實模型只在情境題組與第一張實作 ticket 測得到。
- spec：第一張實作 ticket 是「Azure 實際驗證」；整合層的實作照提案第 11 節的表格開 Draft MR。

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：對話狀態交給 Azure Responses API 保存。介面要能接續上一輪：傳入 `previous_response_id`、回傳新的 response id，每輪重送 instructions；fake 實作要能模擬接續與 id 過期。這偏離 §4.2 的地端切換，提案時附上 ADR 0001 給瑋鋐。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：`integrations/llm` 要支援 function calling：送出工具定義、收到工具呼叫、送回工具結果後再拿最終回覆，而且整段都要能接上 `previous_response_id`。fake 實作要能模擬「回傳工具呼叫」，pytest 才能驗人數必填與「每則訊息最多呼叫 2 次工具」的上限。地端模型對 function calling 的支援程度不一，提案給瑋鋐時一併說明，並附上 ADR 0002。
- 2026-11-07（來自「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」）：embedding 一定要做（主要為展示 RAG）。`integrations/embedding` 要提供文字轉向量：線上每次「查桌遊」工具呼叫轉 1 段 `preference_text`；批次轉心得摘要與心得片段。向量長度依 `EMBEDDING_DIM`；零向量要在這層擋掉（見「RAG 教材有哪些可以重用」）。fake 實作要對同一段文字產生固定向量，pytest 才能驗 RRF 排序。
- 2026-11-08（來自「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」）：離線批次也透過 `integrations/llm` 與 `integrations/embedding`。LLM 要支援固定格式輸出（strict JSON schema），用在三種呼叫：擷取候選詞、合併同義詞、上標籤（代碼是 enum，由詞彙表產生）；心得摘要是純文字。每次全部重跑約轉 15 段心得摘要、約 200 段心得片段，embedding 介面要不要支援一次轉多段在這張決定。輸出不合格時「重試 1 次再跳過」寫在 service，不在整合層。fake 實作要能回傳符合 schema 的固定內容，pytest 才能驗上標籤的三項自動檢查與匯入標籤草稿的「只能刪除」。
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：推薦的最終回覆用 structured outputs（strict JSON schema：`reply`、`recommendations[]`，每筆 `game_id`、`reason`、`excerpt_ids`），而且和 function calling 在同一段對話裡：同一個請求要同時帶 `tools` 與 `text.format`。文件沒有直接範例，這張要在 Azure 實際驗證一次。fake 實作要能回傳符合 schema 的最終回覆，包括不在工具結果裡的 `game_id`、片段 ID，pytest 才能驗「整款丟掉、只丟片段 ID、全部丟掉時換固定文字」。schema 是固定的，不依工具結果動態產生 enum。
