# 對話狀態存在哪裡

Type: grilling
Status: resolved
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

多輪對話的狀態放在哪裡？

- (a) 後端存一筆對話資料，前端每次只送新訊息
- (b) 後端不存，前端每次送完整對話紀錄
- (c) 其他做法

一併決定：

1. 對話是否屬於某位使用者（`user_id`）。
2. 玩家能不能回頭看以前的對話。
3. 對話要保留多久。
4. 誰能看到誰的對話（授權規則，AGENTS.md §4.5）。

## Answer

2026-11-07 和立倫討論後決定。

**選 (c)：對話狀態交給 Azure OpenAI Responses API 保存**，用 `previous_response_id` 接續，後端不存對話。理由、考慮過的做法與後果見 [ADR 0001](../../../docs/adr/0001-games-advisor-conversation-state-in-azure.md)。這個做法偏離 AGENTS.md §4.2 的地端切換，ADR 狀態為 proposed，等組員決定。

1. **`user_id`：對話不屬於任何使用者。** 後端沒有對話資料。前端保管最新一輪的 `response_id`，送新訊息時一起帶上；後端回覆時給新的 `response_id`。
2. **不能回頭看以前的對話。** 重新整理頁面或關掉分頁就是新對話；不提供對話列表，前端也不把訊息存進瀏覽器。
3. **保留期限：Azure 預設 30 天。** 接續需要 `store=true`；我們不主動刪除。
4. **授權：後端不檢查 `response_id` 的擁有者。** id 是很長的隨機字串，內容只有桌遊偏好，API 也沒有讀取歷史訊息的端點。哪些角色能用聊天室，由「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」決定。

邊界情況：

- **`response_id` 過期或無效**：API 回錯誤，前端顯示「對話已失效，請開始新對話」並清空畫面，不默默開一段新對話（否則 Agent 會忘記玩家說過的條件）。錯誤碼由「API 契約與 prototype 頁面」決定。
- **對話長度**：先不設上限。追問輪數的上限由「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」決定。

查證到的事實（2026-11-07）：

- Azure Responses API 支援 `gpt-4.1`、`gpt-4.1-mini`、`gpt-4o-mini`，也支援 structured outputs（`text.format`）與 function calling；只在 31 個區域提供。
- 接續時，前面每一輪的輸入 token 都會重新計費，費用不比前端送完整紀錄少。
- `instructions` 不會跟著 `previous_response_id` 延續，每輪都要重送。

術語：`GLOSSARY.md` 提案區新增「對話」、「訊息」。

來源：

- Microsoft Learn「Azure OpenAI Responses API」：https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses
- OpenAI「Conversation state」：https://developers.openai.com/api/docs/guides/conversation-state
- `instructions` 不延續（二手來源，官方 API reference 沒有直接核對）：https://dev.to/ssukhpinder/openai-responses-api-previousresponseid-instructions-repeat-policy-on-every-turn-1c88
