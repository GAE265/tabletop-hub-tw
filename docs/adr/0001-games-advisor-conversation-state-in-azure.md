---
status: proposed
---

# games_advisor 的對話狀態交給 Azure Responses API 保存

games_advisor 的推薦 Agent 是一個聊天室：玩家和 Agent 對話選出桌遊，不需要回頭看以前的對話。因此對話紀錄不存在我們的後端，而是交給 Azure OpenAI Responses API 在伺服器端保存：前端保管最新一輪的 `response_id`，送出新訊息時一起帶上，後端用 `previous_response_id` 接續上一輪。這和 AGENTS.md §4.2「用 `LLM_PROVIDER` 切換雲端與地端」有出入；立倫判斷這個功能不會換成地端 LLM，所以接受這個限制。§4.2 要不要調整，由組員決定。

## Considered Options

- **後端存對話與訊息**：要資料表、migration 與擁有者授權檢查，但這個功能不需要回看紀錄。
- **前端每次送完整訊息紀錄**：不綁定廠商，token 費用和本方案相同。最後沒有選，因為立倫偏好讓 Azure 保存對話脈絡，請求只帶一句新訊息與 `response_id`。

## Consequences

- `LLM_PROVIDER` 切到地端時，games_advisor 無法運作。
- `integrations/llm` 的介面要能接續上一輪（傳入 `previous_response_id`），fake 實作也要模擬這件事。介面由瑋鋐擁有，要另外提案。
- 接續時，前面每一輪的輸入 token 仍會重新計費，費用不會比送完整紀錄少；`instructions` 不會延續，每輪都要重送。
- 對話紀錄存在 Azure（`store=true`），預設保留 30 天，我們不主動刪除。超過期限的 `response_id` 不能再接續，API 回錯誤，前端請玩家開始新對話。
- 換 Foundry 資源時（例如開發期間各自的 Foundry 整合成一個），進行中的對話全部失效：舊的 `response_id` 在新資源找不到，處理方式和過期相同。
- 後端不檢查 `response_id` 屬於哪位使用者：id 是很長的隨機字串，對話內容只有桌遊偏好，API 也沒有讀取歷史訊息的端點。
