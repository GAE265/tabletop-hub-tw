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
