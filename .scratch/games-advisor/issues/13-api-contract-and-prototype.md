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
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：推薦結果是卡片，最多 3 張，照工具回傳的順序排列。每張卡片有：程式從資料庫填的繁中名稱、人數、時長、年齡、難度；程式比對工具呼叫得出的放寬條件（時長或年齡）；LLM 寫的推薦理由（最多 2 句）；被引用的心得片段（完整原文、`title`、`site_name`、`source_url`，顯示成「文章標題 · 網站名稱」連到原文，英文不翻譯）。這張要決定：回應裡卡片與放寬條件的欄位名稱和位置；`reply` 與卡片怎麼串流（LLM 的最終輸出是 JSON，`reply` 在前）；片段要不要摺疊或截斷；`reply` 被換成固定文字時（推薦全部被丟掉）畫面顯示什麼。追問與離題時沒有卡片。
- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：service 要把整合層的例外轉成 API 錯誤，狀態碼和錯誤碼在這張決定。`LLMConversationNotFound`：用 §4.3 的 404，符合「找不到」。`LLMUnavailable`、`EmbeddingError`（包括 `EmbeddingUnavailable`）：都是 5xx，不在 §4.3 的清單裡；建議用 503，要不要補進 §4.3 由立倫向組員提議。`LLMOutputRejected`（內容過濾、模型拒答、輸出被截斷）：不回 HTTP 錯誤，回一則固定文字的訊息。`LLMError`：不攔截，變成 500。也要決定失敗時回哪個 `response_id`：只有拿到最終輸出時才回新的 id；回 HTTP 錯誤時前端沿用原本的 id，玩家重送即可；回固定文字時，建議回請求帶來的原 id，這樣這則訊息不會算進對話，中途的工具呼叫也不會留下沒送回結果的紀錄。
