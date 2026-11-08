# 專題專用 Foundry 要部署哪些模型

Type: grilling
Status: resolved
Blocked by: 09, 10, 12
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「[確認可用的 Azure OpenAI 資源](04-azure-openai-resources.md)」決定另建一個 tabletop-hub 專用的 Foundry 資源。這張決定裡面要部署什麼：

1. 對話模型與 embedding 模型各用哪一個（候選見該 ticket 的 Answer §2）。條件：支援 structured outputs、繁中品質夠、embedding 維度不超過 pgvector 的索引上限。
2. 區域、部署類型（例如 GlobalStandard）、每個部署的 TPM。
3. 在 NTD 2800 的額度內估算費用：離線批次（心得轉標籤、產生 embedding）與線上對話各會用掉多少。先確認同一個資源群組裡的其他資源是否也從這筆額度扣。
4. 部署名稱與 `EMBEDDING_DIM` 的值。

結論寫進 spec；實際建立資源與部署列為實作 ticket，不在這張做。

## Answer

2026-11-08 與立倫 grilling 定案（3 輪）。Foundry 還沒建，模型依能力分數和 Azure 公開牌價評估後推薦。Azure CLI 的登入過期，配額相關的事實移到建立 Foundry 的實作 ticket（第 8 點）。

**總覽**

| 用途 | 部署名稱 | 模型（版本） | 設定 |
|---|---|---|---|
| 對話 | `gpt-5.6-luna` | gpt-5.6-luna（2026-07-09） | `LLM_MODEL`；`LLM_REASONING_EFFORT=low` |
| 心得管線 | `gpt-5.6-terra` | gpt-5.6-terra（2026-07-09） | `LLM_BATCH_MODEL`；推理強度用模型預設（`medium`） |
| embedding | `text-embedding-3-large` | text-embedding-3-large（1） | `EMBEDDING_MODEL`；`dimensions=1536`；`EMBEDDING_DIM=1536` |

區域 Japan East，部署類型 GlobalStandard。

**1. 對話模型：gpt-5.6-luna**

| 模型 | 綜合能力（BenchLM 總分） | 評估題組跑一次 | 心得管線全部重跑一次 | 狀態 |
|---|---|---|---|---|
| gpt-5.6-terra | 69.8 | 約 NTD 73 | 約 NTD 65 | GA |
| gpt-5.6-luna | 64.0 | 約 NTD 7 | 約 NTD 7 | GA |
| gpt-4.1 | 37.4 | 約 NTD 52 | 約 NTD 36 | Deprecated |
| gpt-4.1-mini | 29.0 | 約 NTD 10 | 約 NTD 7 | Deprecated |

- Artificial Analysis 智能指數：terra 55.0、luna 51.2、gpt-4.1-mini 10.2。gpt-4o-mini 比 gpt-4.1-mini 更舊更弱，不列入。
- 選 luna：比 gpt-4.1-mini 便宜，能力分數卻高一倍以上。terra 總分只高約 6 分，價格約 10 倍；對話是用量最大的部分（開發、評估題組、Demo），而這個功能不追求最高準確率。
- 需要的功能都有文件確認：Microsoft 文件列出 gpt-5.6 系列支援 structured outputs、Responses API、工具呼叫。工具呼叫要走 Responses API；Chat Completions 帶工具時，推理強度只能是 `none`。這更正了「[確認可用的 Azure OpenAI 資源](04-azure-openai-resources.md)」的「文件沒列、未實測」。
- 4.1 系列已 Deprecated：只有部署過該版本的訂用帳戶能再部署，退役時沒有替代模型，部署會直接停用。
- 升級路徑：Demo 題用 luna 過不了時，把 `LLM_MODEL` 改成 `gpt-5.6-terra`（要先建部署），換之前、換之後各跑一次評估題組比較，程式不用改。

**2. 心得管線：gpt-5.6-terra**

- 心得管線決定資料品質：人工驗證只能刪標籤，模型漏掉的標籤補不回來；合併同義詞要把 150–300 個候選詞整理成最多 30 個，是最難的一步。
- 心得管線很少跑，全部重跑一次 terra 只比 luna 多約 NTD 60。
- 用 `LLM_BATCH_MODEL` 指定，批次指令另外建一個 provider（見第 4、6 點）。部署沒用到不收費。

**3. embedding：text-embedding-3-large，縮成 1536 維**

- OpenAI 公布的多語言檢索分數（MIRACL）：small 44.0、large 54.9。評估題組會測「用繁中找英文心得片段」。
- 用 `dimensions=1536` 縮短：`EMBEDDING_DIM` 保持現在的預設值 1536，也低於 pgvector 建索引的 2000 維上限，之後想加索引不用改維度。
- 費用：每 100 萬 token NTD 4.2（small 是 0.6）。全部重跑約 215 段、6.5 萬 token，不到 NTD 1。

**4. 推理強度**

- gpt-5.6 是推理模型，回答前會先思考，思考用的 token 算輸出費；預設強度 `medium`。
- 新增設定 `LLM_REASONING_EFFORT`：有值才在請求帶 `reasoning.effort`，留空就不帶、用模型預設（gpt-4.1 這類非推理模型不接受這個參數）。
- 對話填 `low`：要照對話規則判斷「追問或推薦」「放寬哪一項」，需要一點規劃。心得管線的 provider 不帶，用預設的 `medium`，玩家不用等它。
- `reasoning.context` 不設定，用 gpt-5.6 的預設 `all_turns`：前幾輪的推理內容會帶到下一輪，輸入 token 多一點；luna 很便宜，不另外關掉。
- 速度（Artificial Analysis 量測 luna）：不推理時約 0.8 秒開始輸出；`medium` 約 2 秒；之後每秒約 160–190 token。一則訊息（2 次工具＋1 次回覆）大約 5–10 秒。
- 之後可以用評估題組比較 `none` 與 `low`。

**5. 區域、部署類型、TPM、部署名稱**

- **Japan East**：在 Responses API 的支援區域清單內，三個模型都能用 GlobalStandard 部署，是離台灣最近的區域。
- **GlobalStandard**：照 token 計費，最便宜，預設配額最高。資料可能在全球任一個 Azure 區域處理；心得都是公開資料，沒有影響。
- **TPM**：luna 100K、terra 50K、embedding 100K。配額不夠時，把剩下的全部給它；超過 TPM 時 SDK 會自動重試。
  - luna：評估題組連續跑時每分鐘約 100K。
  - terra：心得管線一次處理一款，每分鐘用不到 50K。
  - embedding：全部重跑約 6.5 萬 token，一次送完。
- Microsoft 文件的配額事實：Tier 1 的 GlobalStandard 預設 luna、terra 各 250K TPM，text-embedding-3-large 1M。最低的 Tier 0 沒有 gpt-5.6 和 text-embedding-3-large；這個訂用帳戶已經有人部署過它們，應該不是 Tier 0。Foundry 的配額正在改成整個訂用帳戶共用一個額度池，其他學員的部署也會算進去。
- **部署名稱和模型名稱相同**，不加版本。

**6. 逾時**

- 對話 `LLM_TIMEOUT_SECONDS=30`（整合層提案的預設值從 60 改成 30）。luna 用 `low` 時，一次呼叫通常 10 秒內完成。
- 前端的等待上限 100 秒，比 3 × 30 = 90 秒長（「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」第 4 點的規則）。
- 心得管線 300 秒，寫在批次指令裡，不另外開設定。合併同義詞那次輸入最長，terra 用 `medium` 可能要一兩分鐘。

**7. 費用估算**

- 額度是 **NTD 3000**（立倫更正；「確認可用的 Azure OpenAI 資源」寫的 2800 是舊數字）。
- Azure 公開牌價（新台幣，每 100 萬 token，GlobalStandard）：

| 模型 | 輸入 | 快取輸入 | 輸出 |
|---|---|---|---|
| gpt-5.6-luna | 6.5 | 0.65 | 38.9 |
| gpt-5.6-terra | 64.8 | 6.5 | 389.1 |
| gpt-4.1 | 64.8 | 16.2 | 259.4 |
| gpt-4.1-mini | 13.0 | 3.2 | 51.9 |
| text-embedding-3-large | 4.2 | — | — |

- 估算的假設：一則訊息平均輸入約 1.4 萬 token（「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」的評估題組量級）、輸出約 1,400 token（含推理）；心得管線全部重跑一次輸入約 40 萬、輸出約 10 萬 token（含推理）。
- 情境：開發加 Demo 共 500 則訊息（約 NTD 75）、評估題組跑 10 次（約 NTD 70）、心得管線重跑 5 次（約 NTD 325）、embedding（不到 NTD 5）。合計約 **NTD 475，佔 16%**。全部改用 gpt-4.1 約 NTD 1,200。
- 這些數字沒有扣快取折扣，是上限。gpt-5.6 寫入快取時收輸入價的 1.25 倍，讀取快取只收 0.1 倍。`LLMResponse` 會帶 token 用量，可以拿實際用量對照。

**8. 移到建立 Foundry 的實作 ticket**

登入 Azure 才能查的 3 件事，在建立資源時確認：

1. 訂用帳戶的配額等級，以及第 5 點的 TPM 夠不夠。
2. NTD 3000 是不是和資源群組裡其他資源共用。
3. 有沒有限制區域的 policy；有的話，從允許的區域中挑支援 Responses API、三個模型都能部署的。

保險規則：如果查到剩下的額度不到 NTD 1,000，心得管線改用 luna（`LLM_BATCH_MODEL` 留空）。

建好後的第一張實作 ticket 照[整合層提案](../integrations-proposal.md)第 10 節，用 `gpt-5.6-luna`、`reasoning.effort: low` 驗證「工具＋固定格式輸出」。

**設定值**（不寫金鑰與真實資源名稱，AGENTS.md §2.1）

```
LLM_PROVIDER=cloud
LLM_ENDPOINT=https://<資源名稱>.openai.azure.com/openai/v1/
LLM_MODEL=gpt-5.6-luna
LLM_BATCH_MODEL=gpt-5.6-terra
LLM_REASONING_EFFORT=low
LLM_TIMEOUT_SECONDS=30
EMBEDDING_PROVIDER=cloud
EMBEDDING_ENDPOINT=（和 LLM_ENDPOINT 相同）
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIM=1536
```

**留給其他 ticket 的事**

- 「[確認可用的 Azure OpenAI 資源](04-azure-openai-resources.md)」：更正額度（NTD 3000）與 gpt-5.6 的功能支援，寫在該張 Comments。
- 「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」：選定的 embedding 模型與維度，寫在該張 Comments。
- [整合層提案](../integrations-proposal.md)：已補上 `LLM_REASONING_EFFORT`、`LLM_BATCH_MODEL`、批次逾時，`LLM_TIMEOUT_SECONDS` 預設改成 30。
- spec：上面的設定值、前端等待上限 100 秒；實作 ticket 要列「建立 Foundry 與三個部署」（含第 8 點的確認項目），排在整合層第 10 節的驗證之前。

**來源**

- Azure Retail Prices API（`currencyCode=TWD`）：https://prices.azure.com/api/retail/prices
- Microsoft Learn「Azure OpenAI reasoning models」（gpt-5.6 的功能表、推理強度、`reasoning.context`）：https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
- Microsoft Learn「Use the Azure OpenAI Responses API」（支援區域與模型）：https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses
- Microsoft Learn「Region availability for Foundry Models sold by Azure」：https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard
- Microsoft Learn「Azure OpenAI quotas and limits」（配額等級）：https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits
- Microsoft Learn「Model retirement schedule」：https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule
- BenchLM：https://benchlm.ai/models/gpt-5-6-luna 、https://benchlm.ai/models/gpt-4-1-mini
- Artificial Analysis（luna 速度）：https://artificialanalysis.ai/models/gpt-5-6-luna-medium/providers

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：對話模型要透過 Responses API 呼叫，Foundry 的區域要在 Responses API 的支援清單內。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：對話模型要支援 function calling（Responses API 的 tools），也要能在每輪重送的 instructions 下遵守對話規則。
- 2026-11-07（來自「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」）：要部署 embedding 模型。批次用在心得摘要（每款 1 段）與心得片段（約幾百段）；線上每次「查桌遊」工具呼叫轉 1 段 `preference_text`，片段查詢沒有偏好時用存好的摘要向量，不另外呼叫。
- 2026-11-08（來自「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」）：每次全部重跑的呼叫次數：LLM 約 46 次，另加重試（擷取候選詞 15、合併同義詞 1、上標籤 15、心得摘要 15）；embedding 約 215 段（心得摘要 15、心得片段約 200）。歸納詞彙表通常只跑一次，補心得時重跑上標籤、心得摘要、心得片段。合併同義詞那次的輸入最長（150–300 個候選詞）；擷取候選詞、合併同義詞、上標籤都要 strict JSON schema，上標籤的代碼是 enum。
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：對話模型要在同一個 Responses API 請求裡同時支援 function calling 與 structured outputs（最終回覆是 strict JSON schema）。推薦理由要照對話規則只根據工具資料寫，繁中品質會影響情境題組的結果。
- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：要填的設定：`LLM_ENDPOINT`（v1 端點）、`LLM_API_KEY`、`LLM_MODEL`（部署名稱）、`LLM_TIMEOUT_SECONDS`（預設 60）、`EMBEDDING_ENDPOINT`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`。text-embedding-3 系列會帶 `dimensions=EMBEDDING_DIM`。每個 provider 只綁一個部署；批次要用比較大的模型，就加 `LLM_BATCH_MODEL`。合併同義詞那次的輸入最長，如果 60 秒不夠，批次的逾時在這張決定。Foundry 建好後的第一張實作 ticket，是在 Azure 驗證 `tools` 加 `text.format`（[提案](../integrations-proposal.md)第 10 節），所以對話模型的部署要先建好。
- 2026-11-08（來自「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」）：對話 API 不串流，一則訊息最多呼叫 3 次 LLM（2 次工具＋1 次最終回覆）。`LLM_TIMEOUT_SECONDS` 的值決定前端要等多久，前端的等待上限要比 3 × `LLM_TIMEOUT_SECONDS` 長。
- 2026-11-08（來自「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」）：評估題組跑一次大約 50 則訊息（7 題各 1 次、3 題 Demo 題各 3 次），輸入約 70 萬 token，估算額度時要算進去。換模型前後可以各跑一次評估題組比較。
