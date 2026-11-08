# 專題專用 Foundry 要部署哪些模型

Type: grilling
Status: open
Blocked by: 09, 10, 12
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「[確認可用的 Azure OpenAI 資源](04-azure-openai-resources.md)」決定另建一個 tabletop-hub 專用的 Foundry 資源。這張決定裡面要部署什麼：

1. 對話模型與 embedding 模型各用哪一個（候選見該 ticket 的 Answer §2）。條件：支援 structured outputs、繁中品質夠、embedding 維度不超過 pgvector 的索引上限。
2. 區域、部署類型（例如 GlobalStandard）、每個部署的 TPM。
3. 在 NTD 2800 的額度內估算費用：離線批次（心得轉標籤、產生 embedding）與線上對話各會用掉多少。先確認同一個資源群組裡的其他資源是否也從這筆額度扣。
4. 部署名稱與 `EMBEDDING_DIM` 的值。

結論寫進 spec；實際建立資源與部署列為實作 ticket，不在這張做。

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：對話模型要透過 Responses API 呼叫，Foundry 的區域要在 Responses API 的支援清單內。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：對話模型要支援 function calling（Responses API 的 tools），也要能在每輪重送的 instructions 下遵守對話規則。
- 2026-11-07（來自「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」）：要部署 embedding 模型。批次用在心得摘要（每款 1 段）與心得片段（約幾百段）；線上每次「查桌遊」工具呼叫轉 1 段 `preference_text`，片段查詢沒有偏好時用存好的摘要向量，不另外呼叫。
- 2026-11-08（來自「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」）：每次全部重跑的呼叫次數：LLM 約 46 次，另加重試（擷取候選詞 15、合併同義詞 1、上標籤 15、心得摘要 15）；embedding 約 215 段（心得摘要 15、心得片段約 200）。歸納詞彙表通常只跑一次，補心得時重跑上標籤、心得摘要、心得片段。合併同義詞那次的輸入最長（150–300 個候選詞）；擷取候選詞、合併同義詞、上標籤都要 strict JSON schema，上標籤的代碼是 enum。
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：對話模型要在同一個 Responses API 請求裡同時支援 function calling 與 structured outputs（最終回覆是 strict JSON schema）。推薦理由要照對話規則只根據工具資料寫，繁中品質會影響情境題組的結果。
- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：要填的設定：`LLM_ENDPOINT`（v1 端點）、`LLM_API_KEY`、`LLM_MODEL`（部署名稱）、`LLM_TIMEOUT_SECONDS`（預設 60）、`EMBEDDING_ENDPOINT`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`。text-embedding-3 系列會帶 `dimensions=EMBEDDING_DIM`。每個 provider 只綁一個部署；批次要用比較大的模型，就加 `LLM_BATCH_MODEL`。合併同義詞那次的輸入最長，如果 60 秒不夠，批次的逾時在這張決定。Foundry 建好後的第一張實作 ticket，是在 Azure 驗證 `tools` 加 `text.format`（[提案](../integrations-proposal.md)第 10 節），所以對話模型的部署要先建好。
