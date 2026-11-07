# API 契約與 prototype 頁面

Type: prototype
Status: open
Blocked by: 05, 07, 11
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

用粗略的頁面草圖與 API 範例讓立倫反應，決定：

1. API 路徑、HTTP 方法、請求與回應格式、錯誤碼（照 AGENTS.md §4.3）。
2. 推薦結果的資料格式：桌遊、理由、出處。
3. 回覆要不要串流。
4. prototype 頁面（`frontend/lib/prototypes/games_advisor/`）有哪些按鈕與欄位；載入中、沒有資料、錯誤時各顯示什麼。
5. 哪些角色可以使用；沒有權限時回什麼。

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：請求帶新訊息與上一輪的 `response_id`，回應帶新的 `response_id`，欄位名稱在這張決定。要定 `response_id` 過期或無效時的錯誤碼；前端顯示「對話已失效，請開始新對話」並清空畫面。後端不存對話，所以沒有列出或讀取對話的端點。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：一則訊息最多推薦 3 款；service 每則訊息最多呼叫 2 次工具；人數不合理時由 LLM 向玩家確認，不回 HTTP 錯誤。推薦結果的格式要讓程式能檢查「只推薦工具回傳的桌遊」（可能和「推薦理由要寫什麼」一起決定）。離題規則：問規則或玩法時請玩家改用規則問答（`rules_qa`），prototype 頁面可以考慮放連結。
