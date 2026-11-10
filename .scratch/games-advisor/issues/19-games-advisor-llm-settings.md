# LLM 設定也改成 games_advisor 自己的一組嗎

Type: grilling
Status: resolved
Blocked by: 18
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」決定 embedding 改用 `games_advisor` 自己的設定（`GAMES_ADVISOR_EMBEDDING_*`）。同樣的理由可能也適用 LLM：[整合層提案](../integrations-proposal.md)第 7 節的 `LLM_*` 是全域設定，目前指向只有立倫使用的 Foundry。

立倫說明：開發期間，立倫和組員各用自己的 LLM、embedding 模型與 PostgreSQL，可能各自有一個 Foundry project；最後可能整合成一個 Foundry，也可能維持多個 Foundry 與 PostgreSQL。

要決定：

1. `games_advisor` 的 LLM 要不要也用自己的一組設定（例如 `GAMES_ADVISOR_LLM_*`）。要的話，哪些欄位分開：provider、endpoint、金鑰、對話模型、批次模型（`LLM_BATCH_MODEL`）、推理強度、逾時。
2. 整合層提案的 `get_llm_provider` 要不要比照 `get_embedding_provider`，改成接收設定值、不讀 `Settings`。
3. 全域的 `LLM_PROVIDER`（`core/config.py` 已經有）和讀它的既有測試怎麼處理，例如 `test_unimplemented_provider_raises_clear_error`。
4. 對話狀態存在 Azure（ADR 0001，proposed）：換 Foundry 後，前端帶來的舊 `response_id` 會變成 404（「API 契約與 prototype 頁面」定了前端清空對話）。要不要額外處理，還是接受。

## Answer

2026-11-08 與立倫 grilling 定案（3 輪）。

**總覽**

- LLM 不另開 games_advisor 自己的設定，繼續用全域 `LLM_*`（[整合層提案](../integrations-proposal.md)第 7 節）。只有 embedding 是例外（`GAMES_ADVISOR_EMBEDDING_*`）。
- factory 照提案的 `get_llm_provider(name, settings)`，不新增 `LLMConfig`。批次指令複製一份 settings、換掉三個值。
- 沒設定模型時，fake 讓對話 API 回 503，需要 LLM 的批次指令拒絕執行。
- 換 Foundry 後舊對話走既有的 404 清空，不另外處理。

**1. LLM 用全域設定，只有 embedding 開例外（ticket 第 1 題）**

- 理由（立倫提出）：換 embedding 模型，存進資料庫的向量就不能和新向量比較；合併進同一個資料庫時，其他 domain 可能用不同的 embedding 模型。換 LLM 模型時，存下的心得摘要與標籤仍然有效，沒有資料相容問題。
- 好處：LLM 照 AGENTS.md §4.2 用 `LLM_PROVIDER` 切換，沒有新的出入；要請瑋鋐確認的事少一件。
- 取捨：開發期間每人用自己的 `.env`，全域設定不會互相影響。只有最後部署成同一套環境時才會衝突：如果維持多個 Foundry，或其他 domain 要不同的模型、推理強度，再改成 games_advisor 自己的欄位。到時只改設定名稱，資料不用動。
- map Notes 的固定偏好改成只限 embedding：「embedding 的設定與向量不要假設和組員共用；LLM 用全域 `LLM_*`」。
- 沒有採用的方案：7 個欄位全部分開的 `GAMES_ADVISOR_LLM_*`（provider、endpoint、金鑰、對話模型、批次模型、推理強度、逾時）。

**2. factory 不改（ticket 第 2 題）**

- `get_llm_provider(name: str, settings: Settings | None = None)` 照提案，整合層讀全域 settings。LLM 讀的是全域欄位，整合層讀它不會因此知道 domain（AGENTS.md §4.2）；embedding 讀的是 games_advisor 自己的欄位，所以才要用 `EmbeddingConfig`。兩種寫法不同是有理由的。
- 批次指令（歸納詞彙表、上標籤、產生心得摘要）建 LLM 時，複製一份 settings 再交給 factory：

```python
batch_settings = settings.model_copy(update={
    "llm_model": settings.llm_batch_model or settings.llm_model,
    "llm_reasoning_effort": None,   # 用模型預設
    "llm_timeout_seconds": 300,
})
llm = get_llm_provider(settings.llm_provider, batch_settings)
```

- 這段寫成 games_advisor 裡的一個小函式，用單元測試確認三個值都換對。`model_copy` 換值時不會重新驗證，但換進去的三個值都合法。
- 沒有採用的方案：
  - `get_llm_provider(config: LLMConfig)`，比照 embedding：要多一個型別，既有測試要改 4 個。
  - 維持 settings，另外加 `model=`、`reasoning_effort=`、`timeout=` 參數覆蓋：建立 LLM 會有兩種寫法。

**3. 全域 `LLM_PROVIDER` 與既有測試（ticket 第 3 題）**

- 全域 `LLM_PROVIDER` 保留，後端照樣用它建 `app.state.llm`，games_advisor 也用它。
- 既有測試只改提案第 9 節第 2 點原本列的 2 個（`cloud` 實作後，參數改成 `local`），不多改。

**4. 沒設定模型時（用 fake）**

- 對話 API：`FakeLLMProvider` 沒給腳本（`responses=None`）時，`respond` 拋 `LLMUnavailable("沒有設定模型")`，service 照既有規則回 503 `GAMES_ADVISOR_UNAVAILABLE`。`json_outputs=None` 時 `generate_json` 同理。腳本有給但用完，仍然是 `AssertionError`（測試寫錯）。組員、CI、永傑沒有金鑰時就是這種情況；三種選項都看不到卡片（桌遊資料的 JSON 在 repo 外），永傑看參考畫面與交接說明的截圖。
- 批次指令：歸納詞彙表、上標籤、產生心得摘要、評估題組在 `LLM_PROVIDER=fake` 時拒絕執行，印出「需要真的模型，請設定 LLM_*」。理由：fake 的 `generate` 回固定文字，「產生心得摘要」會把 15 款都蓋成同一句話；忘了填 `.env`（例如換了 worktree）時最容易發生。`local` 不擋：前三個指令只用 `generate`、`generate_json`，地端也能做；評估題組遇到 `local` 本來就會拋 `NotImplementedError`。pytest 直接把 fake 傳進指令的函式，不經過這個檢查。「產生心得片段」只用 embedding，不受影響。
- 沒有採用的方案：接受 500（`AssertionError`）；games_advisor 內建一段固定回覆給開發用。

**5. 換 Foundry 後的舊對話（ticket 第 4 題）**

- 接受，不另外處理：舊 `response_id` 在新資源找不到，回 404，前端清空畫面、請玩家開始新對話（「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」已定）。換 Foundry 只在開發與整合時發生。
- 整合層只要 Azure 表示找不到這個 `previous_response_id`，一律轉成 `LLMConversationNotFound`，不分過期、亂填、別的資源產生的；實際狀態碼照提案第 10 節第 4 點的驗證。不然 Azure 對別的資源的 id 如果回 400，會變成 500，前端沿用舊 id，玩家重送幾次都失敗。
- `cloud` 和 `fake` 互換也走同一條路：fake 不認得 Azure 的 id，拋 `LLMConversationNotFound`（提案 6.1 已定）。
- ADR 0001 的 Consequences 補一行「換 Foundry 資源時，進行中的對話全部失效」。

**6. 共用的文件規範**

- 這張 ticket 不改 `AGENTS.md`、`.env.example`、`core/config.py` 或整合層的 factory。
- 另外發現：實作 ticket 12 的提案後，`openspec/specs/llm-provider/spec.md` 會過期（規格寫只有 `generate`、「骨架階段只支援 fake」、`cloud` 要報「尚未實作」）。提案第 9 節加第 6 點：實作的人開一個 OpenSpec change 更新這份規格。

**術語**：`GLOSSARY.md` 不變。

**留給其他 ticket 的事**

- [整合層提案](../integrations-proposal.md)：已改第 5 節（`LLMConversationNotFound` 的範圍）、6.1（沒給腳本時拋 `LLMUnavailable`）、7（LLM 用全域設定、批次指令複製 settings）、9（第 6 點 OpenSpec 規格）、10（第 4 點的轉換規則）、11.2（fake 沒給腳本的測試）。
- 「[需要整合層提供哪些介面](12-integrations-interface.md)」：上面的提案變動寫在該張 Comments。
- [ADR 0001](../../../docs/adr/0001-games-advisor-conversation-state-in-azure.md)：已補換 Foundry 的後果。
- `spec.md`：沒設定模型時對話 API 回 503；4 個批次指令遇到 `LLM_PROVIDER=fake` 拒絕執行；批次指令複製 settings 的小函式與單元測試。

## Comments

- 2026-11-08 grilling 進行中（第 1 輪）：立倫改成只有 embedding 開例外，LLM 繼續用全域 `LLM_*`（整合層提案第 7 節照原樣）。理由：換 embedding 模型會讓存進資料庫的向量無法比較；換 LLM 模型時，存下的心得摘要與標籤仍然有效，沒有資料相容問題。取捨：最後部署如果維持多個 Foundry，或其他 domain 要不同的模型、推理強度，再改成 games_advisor 自己的欄位，只改名稱、不動資料。沒設定模型時，fake 沒給腳本（`responses=None`）的 `respond`、`generate_json` 拋 `LLMUnavailable("沒有設定模型")`，對話 API 回 503 `GAMES_ADVISOR_UNAVAILABLE`；腳本用完仍然是 `AssertionError`。需要 LLM 的 4 個指令（歸納詞彙表、上標籤、產生心得摘要、評估題組）用 fake 時拒絕執行，條件寫法待定。換 Foundry 後舊 `response_id` 走既有的 404 清空，不另外處理；整合層把「找不到 `previous_response_id`」一律轉成 `LLMConversationNotFound`（不分過期、亂填、別的資源）；ADR 0001 的 Consequences 補「換 Foundry 資源時，進行中的對話全部失效」。
- 2026-11-08 grilling 進行中（第 2 輪）：map Notes 的固定偏好改成只限 embedding。需要 LLM 的 4 個指令在 `LLM_PROVIDER=fake` 時拒絕執行（`local` 不擋，評估題組遇到 `local` 本來就會拋 `NotImplementedError`）。立倫提出：原本 `get_llm_provider(name, settings)` 讀全域設定的寫法，應該就能讓批次指令換掉部署、推理強度、逾時，不需要 `LLMConfig`；待確認。
- 2026-11-08 grilling（第 3 輪）：立倫確認批次指令照原本的 settings 寫法，複製一份 settings 換掉三個值，不新增 `LLMConfig`。立倫問這張會不會改到共用的文件規範：不會；但實作 ticket 12 的提案後，`openspec/specs/llm-provider/spec.md` 會過期，提案第 9 節加第 6 點。
