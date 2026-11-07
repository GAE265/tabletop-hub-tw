# 需要整合層提供哪些介面

Type: grilling
Status: open
Blocked by: 04, 07, 10
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

列出 games_advisor 需要 `integrations/llm` 與 `integrations/embedding` 提供的介面：函式名稱、輸入、輸出、錯誤情況、fake 實作的行為。

現況：

- `LLMProvider` 只有 `generate(prompt: str) -> str`（`backend/app/integrations/llm/base.py`），不能傳多輪訊息，也不能要求固定格式輸出。
- `integrations/embedding/` 不存在。
- `LLM_PROVIDER=cloud` 尚未實作（`backend/app/integrations/llm/factory.py`）。

產出：一份給瑋鋐（`integrations/` 擁有者）的介面提案。整合層由誰實作，提案時再談；games_advisor 內的程式由立倫寫。

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：對話狀態交給 Azure Responses API 保存。介面要能接續上一輪：傳入 `previous_response_id`、回傳新的 response id，每輪重送 instructions；fake 實作要能模擬接續與 id 過期。這偏離 §4.2 的地端切換，提案時附上 ADR 0001 給瑋鋐。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：`integrations/llm` 要支援 function calling：送出工具定義、收到工具呼叫、送回工具結果後再拿最終回覆，而且整段都要能接上 `previous_response_id`。fake 實作要能模擬「回傳工具呼叫」，pytest 才能驗人數必填與「每則訊息最多呼叫 2 次工具」的上限。地端模型對 function calling 的支援程度不一，提案給瑋鋐時一併說明，並附上 ADR 0002。
- 2026-11-07（來自「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」）：embedding 一定要做（主要為展示 RAG）。`integrations/embedding` 要提供文字轉向量：線上每次「查桌遊」工具呼叫轉 1 段 `preference_text`；批次轉心得摘要與心得片段。向量長度依 `EMBEDDING_DIM`；零向量要在這層擋掉（見「RAG 教材有哪些可以重用」）。fake 實作要對同一段文字產生固定向量，pytest 才能驗 RRF 排序。
- 2026-11-08（來自「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」）：離線批次也透過 `integrations/llm` 與 `integrations/embedding`。LLM 要支援固定格式輸出（strict JSON schema），用在三種呼叫：擷取候選詞、合併同義詞、上標籤（代碼是 enum，由詞彙表產生）；心得摘要是純文字。每次全部重跑約轉 15 段心得摘要、約 200 段心得片段，embedding 介面要不要支援一次轉多段在這張決定。輸出不合格時「重試 1 次再跳過」寫在 service，不在整合層。fake 實作要能回傳符合 schema 的固定內容，pytest 才能驗上標籤的三項自動檢查與匯入標籤草稿的「只能刪除」。
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：推薦的最終回覆用 structured outputs（strict JSON schema：`reply`、`recommendations[]`，每筆 `game_id`、`reason`、`excerpt_ids`），而且和 function calling 在同一段對話裡：同一個請求要同時帶 `tools` 與 `text.format`。文件沒有直接範例，這張要在 Azure 實際驗證一次。fake 實作要能回傳符合 schema 的最終回覆，包括不在工具結果裡的 `game_id`、片段 ID，pytest 才能驗「整款丟掉、只丟片段 ID、全部丟掉時換固定文字」。schema 是固定的，不依工具結果動態產生 enum。
