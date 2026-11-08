# 確認可用的 Azure OpenAI 資源

Type: task
Status: resolved
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

games_advisor 要用哪一個 Azure OpenAI 資源？確認並記錄：

1. 資源屬於誰（專題共用、課程提供、個人），組員能不能共用。
2. 可用的 chat 模型部署名稱與版本，是否支援固定格式輸出（structured outputs 或 JSON mode）。
3. 可用的 embedding 模型部署名稱與向量維度。`EMBEDDING_DIM` 目前預設 1536（`backend/app/core/config.py`）。
4. 額度或用量限制。

金鑰與 endpoint 只放 `.env`。Answer 只寫設定欄位名稱與部署名稱，不寫金鑰。

## Answer

### 1. 資源歸屬：另建專題專用 Foundry，只有立倫使用

- 訂用帳戶由課程提供。立倫的權限只限自己的學員資源群組（「學生角色」），每位學員各有一個資源群組，組員看不到彼此的資源。
- games_advisor 的金鑰只放立倫的 `.env`，不和組員共用。
- 不沿用既有的 5 個資源（其他課程與專案在用），另建一個 tabletop-hub 專用的 Foundry 資源。要部署哪些模型，由「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」決定。

### 2. 這個訂用帳戶能部署的模型（從既有部署查到）

| 模型 | 版本 | structured outputs |
|---|---|---|
| `gpt-4.1-mini` | 2025-04-14 | 支援（Microsoft 文件的支援清單有列） |
| `gpt-4.1` | 2025-04-14 | 支援 |
| `gpt-4o-mini` | 2024-07-18 | 支援 |
| `gpt-5.6-terra`、`gpt-5.6-luna` | 2026-07-09 | 文件的支援清單沒列，未實測 |
| `text-embedding-3-small` | 1 | 不適用；預設 1536 維 |
| `text-embedding-3-large` | 1 | 不適用；預設 3072 維，可用 `dimensions` 參數縮短 |

- 既有部署都是 GlobalStandard（依用量計費）。
- `EMBEDDING_DIM` 預設 1536，等於 `text-embedding-3-small` 的原生維度。pgvector 的 `vector` 欄位最多只能用 2000 維建 HNSW／IVFFlat 索引；用 `text-embedding-3-large` 要縮短維度，或改用 `halfvec`。
- Azure 的 structured outputs 要求物件的所有欄位都列為 required，並設 `additionalProperties: false`；選填欄位要寫成可為 `null`。這會影響「需要整合層提供哪些介面」的設計。

### 3. 額度

- 課程訂用帳戶的金額上限是 NTD 2800。
- TPM 由新 Foundry 的部署設定決定。

### 4. 設定欄位

- 現有：`LLM_PROVIDER`、`LLM_API_KEY`、`EMBEDDING_DIM`（`.env.example`）。
- 還缺：Azure endpoint、對話模型與 embedding 的部署名稱。欄位怎麼命名，在「需要整合層提供哪些介面」和瑋鋐談。

### 來源

- Azure CLI 唯讀查詢：`az cognitiveservices account list`、`account deployment list`、`account list-models`。
- Microsoft Learn「How to use structured outputs with Azure OpenAI」的 Supported models：https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs

## Comments

- 2026-11-08（來自「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」）：更正兩件事。一、課程額度是 NTD 3000，不是 2800（立倫更正）。二、Microsoft 文件現在已列出 gpt-5.6-terra、gpt-5.6-luna 支援 structured outputs、Responses API 與工具呼叫；工具呼叫要走 Responses API。另外，gpt-4.1、gpt-4.1-mini、gpt-4o-mini 已進入 Deprecated：只有部署過該版本的訂用帳戶能再部署。
