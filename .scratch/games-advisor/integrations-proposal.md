# 提案：`integrations/llm` 與 `integrations/embedding` 的介面

- 提案人：立倫（`games_advisor` 主責）
- 對象：瑋鋐（`integrations/llm/`、`integrations/embedding/` 擁有者，AGENTS.md §3）
- 來源：「[需要整合層提供哪些介面](issues/12-integrations-interface.md)」
- 不在本提案範圍：整合層由誰實作（另外和瑋鋐談）、地端實作（AGENTS.md §1 列為加分，之後再做）

## 1. 為什麼要改

現況：

- `LLMProvider` 只有 `generate(prompt: str) -> str`（`backend/app/integrations/llm/base.py`）。不能接續對話、不能用工具（function calling），也不能要求固定格式的輸出。
- `integrations/embedding/` 不存在。
- `LLM_PROVIDER=cloud` 還沒實作（`backend/app/integrations/llm/factory.py`）。

`games_advisor` 需要整合層支援兩種用途：

| 用途 | 誰呼叫 | 需要 |
|---|---|---|
| 推薦 Agent 的對話 | `games_advisor` service，每則玩家訊息呼叫 1–3 次 | 接續上一次呼叫（`previous_response_id`）、工具（「查桌遊」）、最終訊息符合 strict JSON schema |
| 離線批次 | `games_advisor` 的後端指令 | 符合 strict JSON schema 的輸出（擷取候選詞、合併同義詞、上標籤）、純文字（心得摘要）、批次 embedding（每次全部重跑約 215 段） |
| 「查桌遊」工具 | `games_advisor` service，每次工具呼叫 1 次 | 把 1 段偏好描述轉成向量 |

相關的設計決定：

- [ADR 0001：對話狀態交給 Azure Responses API 保存](../../docs/adr/0001-games-advisor-conversation-state-in-azure.md)（accepted）
- [ADR 0002：追問與推薦由 LLM 依對話規則決定](../../docs/adr/0002-games-advisor-llm-driven-conversation-flow.md)（accepted）

## 2. 設計原則

1. **整合層一次只呼叫 1 次模型。** 工具迴圈、「每則訊息最多呼叫 2 次工具」、人數檢查都是 `games_advisor` 的規則，寫在 service。整合層不知道任何 domain（AGENTS.md §4.2）。
2. **無狀態和有狀態分成不同方法。** `generate`、`generate_json` 不保存任何東西，地端也能實作。`respond` 依賴 Azure 保存對話，只有雲端實作。
3. **schema 一律用 JSON Schema dict。** 由呼叫端寫成符合 Azure strict 規定的格式，整合層不轉換、不驗證。理由：工具參數的 enum 和上標籤的代碼 enum，都要從資料庫動態產生。
4. **整合層的例外不帶 HTTP 狀態碼。** 不繼承 `core.errors.AppError`，由呼叫端的 service 自己轉換。
5. **全部用同步寫法**，和資料庫存取一致（AGENTS.md §4.4）。

## 3. LLM 介面

### 3.1 型別（`integrations/llm/types.py`）

```python
@dataclass(frozen=True)
class JsonSchema:
    name: str      # Azure 規定只能用英數字、底線、連字號
    schema: dict   # 呼叫端負責：所有欄位都列為 required、additionalProperties: false、
                   # 選填欄位寫成可為 null

@dataclass(frozen=True)
class ToolSpec:           # 送給模型的工具定義
    name: str
    description: str
    parameters: dict      # JSON Schema，規定同 JsonSchema.schema

@dataclass(frozen=True)
class ToolCall:           # 模型要求呼叫工具
    call_id: str
    name: str
    arguments: dict

@dataclass(frozen=True)
class ToolResult:         # 呼叫端執行工具後送回的結果
    call_id: str
    output: dict          # 整合層負責轉成 JSON 字串（ensure_ascii=False）

@dataclass(frozen=True)
class LLMResponse:        # respond() 一次呼叫的結果
    response_id: str
    tool_calls: list[ToolCall]   # 模型要求呼叫工具時不是空的
    output: dict | None          # 模型的最終輸出，符合 output_schema
    input_tokens: int
    output_tokens: int
```

- `tool_calls` 與 `output` 一定剛好只有一個有值。
- `LLMResponse` 不叫 `Turn`，因為 `turn` 是 AGENTS.md §10.2 的「回合」。
- `input_tokens`、`output_tokens` 讓呼叫端記 log，用來追蹤額度。依 ADR 0001，接續對話時，前面所有呼叫的輸入 token 每次都會重新計費。

### 3.2 方法（`integrations/llm/base.py`）

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str: ...
        # 既有，簽名不變。批次的心得摘要用它。

    @abstractmethod
    def generate_json(self, *, instructions: str, input: str,
                      schema: JsonSchema) -> dict: ...
        # 無狀態。批次的擷取候選詞、合併同義詞、上標籤用它。

    @abstractmethod
    def respond(self, *, instructions: str,
                input: str | list[ToolResult],
                tools: list[ToolSpec],
                output_schema: JsonSchema,
                previous_response_id: str | None,
                allow_tool_calls: bool = True) -> LLMResponse: ...
        # 有狀態。推薦 Agent 的對話用它。
```

### 3.3 行為規則（雲端實作）

| 規則 | `generate` | `generate_json` | `respond` |
|---|---|---|---|
| Azure 端點 | Responses API | Responses API | Responses API |
| `store` | false | false | true（ADR 0001） |
| `instructions` | 不適用 | 每次都送 | 每次都送（Responses API 不會沿用上一次的 instructions） |
| 輸出格式 | 純文字 | `text.format`：`json_schema`、`strict: true` | 同左，用 `output_schema` |
| 工具 | 無 | 無 | 每個工具都 `strict: true`；`parallel_tool_calls: false` |
| `allow_tool_calls=False` | 不適用 | 不適用 | 照樣送出 `tools`，但帶 `tool_choice: "none"`，保證拿到最終輸出 |
| 推理強度 | 有設定才帶 `reasoning.effort` | 同左 | 同左 |

- 推理強度：provider 建立時帶入（對話的 provider 讀 `LLM_REASONING_EFFORT`），三個方法都一樣。沒有值就不帶 `reasoning`，用模型預設；gpt-4.1 這類非推理模型不接受這個參數。對話用的 gpt-5.6-luna 填 `low`（「[專題專用 Foundry 要部署哪些模型](issues/17-foundry-model-deployments.md)」）。

- `parallel_tool_calls` 固定 false：OpenAI 文件寫明 structured outputs 不相容平行工具呼叫；而且模型同時送出兩個查詢，會打亂呼叫端「先查，查到 0 款才放寬條件」的順序。
- `input` 是字串時，代表玩家的訊息；是 `list[ToolResult]` 時，轉成 Responses API 的 `function_call_output` 項目。
- 呼叫端的迴圈（寫在 service，不在整合層）：

```
第 1 次 respond(input=玩家訊息, previous_response_id=前端帶來的 id)
  → 有 tool_calls：service 執行「查桌遊」
第 2 次 respond(input=[ToolResult], previous_response_id=第 1 次的 id)
  → 有 tool_calls：service 再執行一次（放寬條件）
第 3 次 respond(input=[ToolResult], previous_response_id=第 2 次的 id, allow_tool_calls=False)
  → output：推薦 Agent 的最終訊息
```

## 4. Embedding 介面（`integrations/embedding/base.py`）

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- 只有批次版。線上只轉 1 段時，傳長度 1 的 list。
- 回傳的順序、筆數和 `texts` 相同；傳入空的 list 就回傳空的 list，不發請求。
- 一個請求最多送幾段，由實作決定，呼叫端不用管。
- 每個向量的長度都等於建立 provider 時傳入的 `dim`（`games_advisor` 傳 `GAMES_ADVISOR_EMBEDDING_DIM`，見第 7 節）。text-embedding-3 系列的雲端實作帶 `dimensions=dim`。
- 傳入的文字有空字串或只有空白時，拋 `ValueError`。
- 回傳零向量或維度不符時，拋 `EmbeddingError`。這個檢查寫成所有實作共用的函式，fake 也會檢查。

## 5. 錯誤

`integrations/llm/errors.py`：

| 例外 | 什麼時候 | `games_advisor` 怎麼接 |
|---|---|---|
| `LLMError` | 基底類別。也用在設定或程式錯誤，例如金鑰錯誤（401）、schema 不符合 strict 規定（400） | 不攔截，變成 500 |
| `LLMUnavailable(LLMError)` | 逾時、連線失敗、429、5xx，SDK 重試 2 次後仍然失敗 | 對話：回 HTTP 錯誤；批次：該款列進報告 |
| `LLMConversationNotFound(LLMError)` | Azure 找不到 `previous_response_id`：過期、亂填，或別的 Foundry 資源產生的，一律用這個 | 回「對話已失效」錯誤，前端請玩家開始新對話 |
| `LLMOutputRejected(LLMError)` | 被 Azure 內容過濾擋下、模型拒答（refusal）、輸出因 token 上限被截斷、輸出不是合法 JSON | 對話：換成固定文字；批次：重試 1 次，仍然失敗就跳過 |

`integrations/embedding/errors.py`：

| 例外 | 什麼時候 | `games_advisor` 怎麼接 |
|---|---|---|
| `EmbeddingError` | 基底類別。也用在零向量、維度不符 | 對話：整則訊息失敗，不降級；批次：該款列進報告 |
| `EmbeddingUnavailable(EmbeddingError)` | 逾時、連線失敗、429、5xx，重試後仍然失敗 | 同上 |

- 「重試 1 次再跳過」是批次的業務規則，寫在 service，不寫在整合層。整合層只做 SDK 內建的重試，處理暫時性錯誤。
- 線上 embedding 失敗時不降級成「只用結構化分數排序」：embedding 和對話模型在同一個 Foundry 資源上，embedding 失敗時對話模型通常也連不上；降級會多一條程式路徑要測，也會把 RAG 的失敗藏起來。

## 6. Fake 實作

### 6.1 `FakeLLMProvider`

```python
FakeLLMProvider(
    reply: str = DEFAULT_REPLY,                            # generate()，既有行為不變
    json_outputs: list[dict | Exception] | None = None,    # generate_json() 依序回傳
    responses: list[FakeResponse | Exception] | None = None,  # respond() 依序回傳
)

@dataclass
class FakeResponse:
    tool_calls: list[ToolCall] = field(default_factory=list)
    output: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
```

- 腳本的項目是例外時，就拋出那個例外。用來測重試、跳過，以及「對話已失效」。
- `response_id` 由 fake 依序產生：`fake_resp_1`、`fake_resp_2`…。
- 收到不是自己產生過的 `previous_response_id` 時，拋 `LLMConversationNotFound`，用來模擬過期。這種情況不會用掉腳本的項目。
- 每次呼叫的方法名稱與參數都記在 `fake.calls`。測試靠它檢查：每次都有重送 instructions、`previous_response_id` 有接上、第 3 次呼叫是 `allow_tool_calls=False`。
- fake 不檢查 schema，也不檢查 `allow_tool_calls`：腳本寫什麼就回什麼。這樣才能測 service 的防呆，例如收到不在工具結果裡的 `game_id`。
- 腳本用完了還被呼叫，就拋 `AssertionError`，代表測試本身寫錯。
- 根本沒給腳本時（`responses=None`），`respond` 拋 `LLMUnavailable("沒有設定模型")`；`json_outputs=None` 時，`generate_json` 同理。後端用 `LLM_PROVIDER=fake` 啟動時（組員、CI）就是這種 fake，對話 API 因此回 503，不會變成 500（「[LLM 設定也改成 games_advisor 自己的一組嗎](issues/19-games-advisor-llm-settings.md)」）。
- 既有的 `FakeLLMProvider()`、`FakeLLMProvider("你好")` 用法不變。

### 6.2 `FakeEmbeddingProvider`

```python
FakeEmbeddingProvider(
    dim: int,                                     # factory 傳入 EmbeddingConfig.dim
    vectors: dict[str, list[float]] | None = None,
    error: Exception | None = None,
)
```

- 有指定的文字，回傳指定的向量。
- 沒指定的文字，用 sha256 產生固定的單位向量，長度等於 `dim`。同一段文字每次都得到相同的向量。
- 指定的向量長度不等於 `dim` 時，建立 fake 就拋 `ValueError`。
- 指定零向量時，`embed` 拋 `EmbeddingError`（共用的檢查函式）。
- 有設定 `error` 時，每次 `embed` 都拋出它，例如 `EmbeddingUnavailable()`。
- 每次呼叫都記在 `fake.calls`。
- `dim` 一律由呼叫方從設定讀出來再傳入（`games_advisor` 用 `GAMES_ADVISOR_EMBEDDING_DIM`），不寫死（AGENTS.md §4.4）。只有不連資料庫的 service 單元測試，才可以傳比較小的 `dim`。

## 7. 設定欄位

`core/config.py`（立倫擁有）與 `.env.example` 新增以下欄位：

```
LLM_PROVIDER=          # fake | cloud（cloud 指 Azure OpenAI）| local（尚未實作）
LLM_ENDPOINT=          # 格式：https://<資源名稱>.openai.azure.com/openai/v1/
LLM_API_KEY=           # 既有欄位，Settings 還沒讀
LLM_MODEL=             # 對話模型的部署名稱
LLM_BATCH_MODEL=       # 批次指令用的部署名稱；留空就用 LLM_MODEL
LLM_REASONING_EFFORT=  # none | low | medium | high | xhigh | max；留空就用模型預設，非推理模型要留空
LLM_TIMEOUT_SECONDS=   # 單次請求逾時秒數，預設 30
GAMES_ADVISOR_EMBEDDING_PROVIDER=  # fake | cloud；沒填就是 fake
GAMES_ADVISOR_EMBEDDING_ENDPOINT=
GAMES_ADVISOR_EMBEDDING_API_KEY=
GAMES_ADVISOR_EMBEDDING_MODEL=     # embedding 的部署名稱；也記在每個向量上，用來偵測換了模型
GAMES_ADVISOR_EMBEDDING_DIM=       # 沒填就是 1536
```

- **embedding 設定只給 `games_advisor` 用**（「[詞彙表改版或換 embedding 模型時怎麼處理](issues/18-vocabulary-and-embedding-revisions.md)」）：開發期間每位組員各用自己的 LLM、embedding 模型與 PostgreSQL，可能各自有一個 Foundry project；最後可能整合成一個 Foundry，也可能維持多個。`games_advisor` 的 Foundry 只有立倫使用，金鑰不和組員共用。所以本提案不新增全域的 `EMBEDDING_PROVIDER`、`EMBEDDING_ENDPOINT`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`，規則書 RAG 需要時由他們自己提。
- 沒填 `GAMES_ADVISOR_EMBEDDING_*` 時不退回任何全域設定。組員與 CI 不用填，預設就是 fake。
- 既有的全域 `EMBEDDING_DIM` 不動（資料庫骨架的 spec 要求它存在），`games_advisor` 不讀它。
- **LLM 設定是全域的**（「[LLM 設定也改成 games_advisor 自己的一組嗎](issues/19-games-advisor-llm-settings.md)」）：換 embedding 模型會讓存進資料庫的向量無法比較，換 LLM 模型則不會，已存的心得摘要與標籤仍然有效。所以 `games_advisor` 直接讀全域 `LLM_*`，照 AGENTS.md §4.2 用 `LLM_PROVIDER` 切換。開發期間每人用自己的 `.env`，不會互相影響；最後部署如果維持多個 Foundry，或其他 domain 要不同的模型、推理強度，再改成 `games_advisor` 自己的欄位。

- 每個 provider 只綁一個部署，方法不帶 `model` 參數。「[專題專用 Foundry 要部署哪些模型](issues/17-foundry-model-deployments.md)」決定批次用比較大的模型，所以加 `LLM_BATCH_MODEL`：批次指令另外建立一個 provider，部署換成 `LLM_BATCH_MODEL`、不帶推理強度（用模型預設）、逾時 300 秒（寫在批次指令裡，不開設定），介面不用改。做法是複製一份 settings 再交給 factory：

```python
batch_settings = settings.model_copy(update={
    "llm_model": settings.llm_batch_model or settings.llm_model,
    "llm_reasoning_effort": None,
    "llm_timeout_seconds": 300,
})
llm = get_llm_provider(settings.llm_provider, batch_settings)
```
- embedding 不共用 LLM 的 endpoint 與金鑰，之後才能「LLM 用地端、embedding 用雲端」。目前 `GAMES_ADVISOR_EMBEDDING_ENDPOINT`、`GAMES_ADVISOR_EMBEDDING_API_KEY` 和 LLM 填一樣的值即可。
- SDK 預設的逾時是 600 秒，玩家等不了那麼久，所以要設定。預設 30 秒：gpt-5.6-luna 用 `low` 時，一次呼叫通常 10 秒內完成；前端的等待上限是 100 秒，比 3 × 30 秒長。重試次數沿用 SDK 預設的 2 次，不另外開設定。
- `LLM_REASONING_EFFORT` 不是合法值時，啟動失敗。
- 用 v1 端點，不需要 `api-version`（第一張實作 ticket 會驗證）。
- **待瑋鋐確認**：AGENTS.md §4.2 寫「用 `LLM_PROVIDER` 切換……embedding 同理」。`games_advisor` 另外用自己的 `GAMES_ADVISOR_EMBEDDING_PROVIDER` 切換，見第 9 節第 5 點。

Factory：

```python
get_llm_provider(name: str, settings: Settings | None = None) -> LLMProvider
    # fake：不需要 settings。cloud：settings 必填，缺 endpoint、金鑰或 model 時拋 ValueError。
    # local：NotImplementedError。其他值：ValueError。
@dataclass(frozen=True)
class EmbeddingConfig:          # integrations/embedding/factory.py
    provider: str               # fake | cloud
    dim: int
    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None

get_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider
    # fake：只用 dim。cloud：缺 endpoint、金鑰或 model 時拋 ValueError。其他值：ValueError。
```

- `get_embedding_provider` 只收設定值，不讀 `Settings`，整合層因此不知道 `games_advisor` 存在（AGENTS.md §4.2）。由呼叫方用 `GAMES_ADVISOR_EMBEDDING_*` 組出 `EmbeddingConfig`。
- `get_llm_provider` 讀 `Settings`：LLM 讀的是全域欄位，整合層讀它不會因此知道任何 domain。兩個 factory 寫法不同，是因為設定的歸屬不同。
- `main.py` 啟動時建好 `app.state.llm` 與 `app.state.games_advisor_embedding`，批次指令各自再建一個。設定不完整就讓啟動失敗，和現在「`cloud` 尚未實作就啟動失敗」的做法一致。

## 8. 第三方套件

雲端實作使用 `openai` Python SDK，只在 `integrations/llm/cloud.py`、`integrations/embedding/cloud.py` 裡 import（AGENTS.md §4.2）。MR 說明要寫的理由（§2.4）：

- Azure 文件的 Responses API 範例就用這個套件（v1 端點加上 `base_url`）。
- 內建重試與逾時，請求和回應都有型別。
- 其他選項：用 `httpx` 直接打 REST（要從 dev 依賴升成正式依賴，重試、型別、錯誤轉換都要自己寫）；用 Azure 的 `azure-ai-*` 套件（Responses API 的範例比較少）。

## 9. 和 AGENTS.md 的出入

1. **§4.2 用 `LLM_PROVIDER` 切換雲端與地端**：`respond` 依賴 Azure 保存對話（ADR 0001）和 function calling（ADR 0002），只有雲端實作。地端實作的 `respond` 拋 `NotImplementedError`；`generate`、`generate_json`、`embed` 都可以有地端實作。兩份 ADR 已在 2026-11-09 由組員同意（accepted）。
2. **§7.5 不得為了讓測試通過而修改測試**：實作 `cloud` 之後，下面兩個既有測試一定會失敗，要在 MR 說明寫出理由，經審核者同意後修改：

| 既有測試 | 改法 | 理由 |
|---|---|---|
| `test_unimplemented_provider_raises_clear_error`（參數 `cloud`、`local`） | 參數只留 `local` | `cloud` 已經實作；「尚未實作的值要明確報錯」的意圖由 `local` 繼續驗證 |
| `test_app_startup_fails_loudly_for_unimplemented_provider`（`llm_provider="cloud"`） | 改成 `llm_provider="local"` | 同上；「尚未實作就啟動失敗」的意圖不變 |

3. **§4.3 錯誤狀態碼**：`LLMUnavailable`、`EmbeddingError` 在對話 API 會變成 5xx，不在 §4.3 列出的狀態碼裡。用哪個狀態碼由「[API 契約與 prototype 頁面](issues/13-api-contract-and-prototype.md)」決定。
4. **§2.1 repo 是公開的**：本提案和 `.env.example` 都不寫真實的資源名稱、endpoint 或金鑰。
5. **§4.2「embedding 同理」**：條文的意思是 embedding 也用一個全專案的設定切換雲端與地端。`games_advisor` 改用自己的一組 `GAMES_ADVISOR_EMBEDDING_*`，理由見第 7 節：組員各用自己的資源開發，最後也不一定整合成一個 Foundry 或一個 PostgreSQL。切換雲端、地端的能力不變，只是設定只屬於 `games_advisor`。LLM 沒有這個出入，照 §4.2 用全域 `LLM_PROVIDER`。
6. **OpenSpec 規格 `openspec/specs/llm-provider/spec.md`**：骨架階段寫的規格只有 `generate(prompt)`，並規定「骨架階段只支援 `fake`」、`LLM_PROVIDER=cloud` 要報「尚未實作」。實作本提案後這兩條都不成立，要更新的內容：加上 `generate_json`、`respond`；改成「`fake`、`cloud` 已實作，`local` 尚未實作」。AI 不修改 `openspec/` 資料夾，由實作的人在 MR 說明建議組員更新（2026-11-11）。

## 10. 要在 Azure 實際驗證的事（第一張實作 ticket）

等專題專用的 Foundry 建好，部署好對話模型（`gpt-5.6-luna`，`reasoning.effort: low`）之後，手動執行一次，不放進 pytest：

1. 同一個請求同時帶 `tools`（strict）與 `text.format`（strict json_schema）時：模型會呼叫工具；送回工具結果並接上 `previous_response_id` 後，最終輸出符合 schema。
2. 已經有工具呼叫紀錄的對話，帶 `tool_choice: "none"` 時，模型不會再呼叫工具。
3. v1 端點不帶 `api-version` 也能呼叫。
4. `previous_response_id` 無效時，Azure 實際回的狀態碼和錯誤格式，用來寫 `LLMConversationNotFound` 的轉換。轉換規則：只要 Azure 表示找不到這個 id 就轉換，不分過期、亂填、別的 Foundry 資源產生的（換 Foundry 時會遇到）。
5. 內容過濾擋下輸入、擋下輸出時，Azure 分別回什麼。

**備案**：如果第 1 點不成立，最終輸出改成由一個「交卷」工具 `submit_recommendations` 帶出，工具參數就是原本的 `output_schema`。service 收到這個工具呼叫，就當成最終輸出，不送回結果。介面只改一處：`respond` 的 `output_schema` 改成可以不帶。

驗證結果記在「[建立 Foundry 並在 Azure 驗證](../games-advisor-impl/issues/02-foundry-and-azure-checks.md)」。之後要重新確認（例如換 Foundry），改跑 §11.6 的外部服務測試。

## 11. 測試案例（AGENTS.md §7）

實作者可以直接拿這張表開 Draft MR（§7.2）。能不用金鑰寫的測試一律進 CI（AGENTS.md 7.6），所以雲端實作的行為都用手寫的 `FakeAzureTransport`（`httpx.BaseTransport` 的子類別）注入 `openai` client（AGENTS.md 7.5 規定手寫 fake，2026-11-11 從 `MockTransport` 改過來），假造 Azure 的回應，不連網路（§11.4、§11.5）；真的 Azure 只用 §11.6 的 4 個外部服務測試確認連得上。測試資料一律自行編寫（§2.2）。

### 11.1 Factory 與啟動

| 情境 | 操作 | 預期結果 |
|---|---|---|
| `LLM_PROVIDER=fake` | `get_llm_provider("fake")` | 回傳 `FakeLLMProvider` |
| `LLM_PROVIDER=cloud`，設定齊全 | `get_llm_provider("cloud", settings)` | 回傳雲端實作，建立時不發任何請求 |
| `LLM_PROVIDER=cloud`，缺 `LLM_ENDPOINT`、`LLM_API_KEY` 或 `LLM_MODEL` | `create_app(settings)` | 啟動失敗，錯誤訊息指出缺哪個欄位 |
| `LLM_PROVIDER=local` | `get_llm_provider("local")`、`create_app` | `NotImplementedError`（既有測試，參數改成只有 `local`） |
| 未知的 `LLM_PROVIDER` | `get_llm_provider("nope")` | `ValueError`（既有） |
| `LLM_REASONING_EFFORT` 不是合法值 | `create_app(settings)` | 啟動失敗，錯誤訊息指出這個欄位 |
| `EmbeddingConfig(provider="fake", dim=1536)` | `get_embedding_provider(config)` | 回傳 `FakeEmbeddingProvider`，`dim` 等於 1536 |
| `GAMES_ADVISOR_EMBEDDING_*` 都沒填 | `create_app(settings)` | 啟動成功，`app.state.games_advisor_embedding` 是 fake，`dim` 是 1536；不讀全域的 `EMBEDDING_DIM` |
| `GAMES_ADVISOR_EMBEDDING_PROVIDER=cloud`，缺 `GAMES_ADVISOR_EMBEDDING_MODEL` | `create_app(settings)` | 啟動失敗，錯誤訊息指出缺哪個欄位 |
| 未知的 provider | `get_embedding_provider(EmbeddingConfig(provider="nope", dim=1536))` | `ValueError` |

### 11.2 `FakeLLMProvider`

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 腳本是［工具呼叫, 最終輸出］ | `respond` 兩次，第 2 次帶第 1 次的 `response_id` | 第 1 次 `tool_calls` 不是空的、`output` 是 None；第 2 次 `output` 等於腳本內容；兩次的 `response_id` 不同 |
| `previous_response_id` 不是 fake 產生的 | `respond(previous_response_id="resp_expired")` | `LLMConversationNotFound`，腳本沒有被用掉 |
| 腳本項目是例外 | `respond`、`generate_json` | 拋出那個例外 |
| 腳本用完 | 再多呼叫一次 | `AssertionError` |
| 沒給腳本（`FakeLLMProvider()`） | `respond`、`generate_json` | `LLMUnavailable`，訊息說明沒有設定模型 |
| 任何呼叫 | `respond(...)` | `fake.calls` 記下方法名稱與所有參數 |
| `json_outputs` 有兩筆 | `generate_json` 兩次 | 依序回傳兩筆 |
| 既有用法 | `FakeLLMProvider("你好").generate("hi")` | `"你好"`（既有） |

### 11.3 `FakeEmbeddingProvider`

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 沒指定向量的文字 | 同一段文字 `embed` 兩次 | 兩次向量相同，長度等於 `dim`，不是零向量 |
| 有指定向量 | `embed(["想要歡樂爆笑"])` | 回傳指定的向量 |
| 指定的向量長度不等於 `dim` | 建立 fake | `ValueError` |
| 指定零向量 | `embed` | `EmbeddingError` |
| 設定了 `error` | `embed` | 拋出該例外 |
| 傳入空字串 | `embed([""])` | `ValueError` |
| 傳入空的 list | `embed([])` | 回傳 `[]` |

### 11.4 LLM 雲端實作（`FakeAzureTransport`）

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 帶工具與 `output_schema` | `respond(...)`，檢查送出的請求 | `store: true`、有 `instructions`、每個工具 `strict: true`、`parallel_tool_calls: false`、`text.format` 是 strict json_schema、帶 `previous_response_id` |
| 不准再呼叫工具 | `respond(..., allow_tool_calls=False)` | 請求照樣帶 `tools`，並帶 `tool_choice: "none"` |
| 送回工具結果 | `respond(input=[ToolResult(...)])` | 請求的 `input` 是 `function_call_output` 項目，`output` 是 JSON 字串，中文沒有被跳脫 |
| Azure 回工具呼叫 | `respond` | `tool_calls` 帶 `call_id`、`name`、`arguments`（dict）；`output` 是 None；token 用量有值 |
| Azure 回 JSON 文字 | `respond` | `output` 是解析後的 dict，`tool_calls` 是空的 |
| 無狀態的 JSON 輸出 | `generate_json(...)`，檢查送出的請求 | `store: false`、沒有 `tools`、`text.format` 是 strict json_schema；回傳 dict |
| 純文字 | `generate(prompt)` | `store: false`，回傳文字 |
| 有設定推理強度 | 建立 provider 時帶 `low`，再呼叫任一方法 | 請求帶 `reasoning.effort: "low"` |
| 沒有設定推理強度 | 建立 provider 時不帶，再呼叫任一方法 | 請求沒有 `reasoning` 欄位 |
| `previous_response_id` 無效 | Azure 回對應的錯誤（格式依第 10 節驗證結果） | `LLMConversationNotFound` |
| 429、5xx、逾時 | 任一方法，SDK 重試後仍然失敗 | `LLMUnavailable` |
| 內容過濾 | Azure 回 content filter 錯誤，或回應 `incomplete`、原因是 content filter | `LLMOutputRejected` |
| 模型拒答 | 回應帶 refusal | `LLMOutputRejected` |
| 輸出被截斷 | 回應 `incomplete`、原因是 token 上限 | `LLMOutputRejected` |
| 金鑰錯誤 | Azure 回 401 | `LLMError`，不是上面三種子類別 |

### 11.5 Embedding 雲端實作（`FakeAzureTransport`）

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 3 段文字 | `embed(...)`，檢查送出的請求 | 帶部署名稱與 `dimensions`；回傳 3 個向量，順序和輸入相同 |
| 超過單次請求上限的段數 | `embed(...)` | 拆成多個請求，結果順序不變 |
| Azure 回零向量 | `embed` | `EmbeddingError` |
| Azure 回的維度不符 | `embed` | `EmbeddingError` |
| 429、5xx、逾時 | `embed`，重試後仍然失敗 | `EmbeddingUnavailable` |

### 11.6 外部服務測試（`external`，本機）

加上 `@pytest.mark.external`，不在 CI 跑；發 MR 前在本機執行 `uv run pytest -m external`，結果貼在 MR 說明（AGENTS.md 7.6）。目的只是確認真的連得上 Azure、回應格式和 §11.4、§11.5 假造的一致；行為的細節照樣由 `FakeAzureTransport` 的測試負責。

- 設定從 `.env` 讀（`LLM_*`、`GAMES_ADVISOR_EMBEDDING_*`），不從 shell 讀。缺欄位時直接失敗，錯誤訊息指出缺哪個欄位，不用 `skip`。這個 fixture 放在 `backend/tests/integrations/conftest.py`，不放進 `integrations/llm`（#18）。
- 工具、schema、文字都自行編寫，不用桌遊或心得資料。
- 內容過濾不放進來：要臨時改 Azure 的過濾設定才觸發得到（見第 10 節的驗證結果）。
- 跑一次的費用不到 NTD 1（第 10 節驗證時的實測）。

| 情境 | 操作 | 預期結果 |
|---|---|---|
| 工具呼叫與最終輸出 | `respond` 帶一個自編的工具與 `output_schema`，訊息要求先查詢；再送回 `ToolResult`，帶第 1 次的 `response_id` | 第 1 次 `tool_calls` 不是空的；第 2 次 `output` 符合 schema |
| 無狀態的 JSON 輸出 | `generate_json`，自編的 strict schema | 回傳 dict，欄位符合 schema |
| 向量 | `embed` 兩段文字 | 2 個向量，長度都等於 `GAMES_ADVISOR_EMBEDDING_DIM` |
| 對話不存在 | `respond` 帶不存在的 `previous_response_id`：`resp_` 開頭的、亂填的各一次 | 兩次都是 `LLMConversationNotFound` |
