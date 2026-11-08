# API 契約與 prototype 頁面

Type: prototype
Status: resolved
Blocked by: 05, 07, 11
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

用粗略的頁面草圖與 API 範例讓立倫反應，決定：

1. API 路徑、HTTP 方法、請求與回應格式、錯誤碼（照 AGENTS.md §4.3）。
2. 推薦結果的資料格式：桌遊、理由、出處。
3. 回覆要不要串流。
4. prototype 頁面（`frontend/lib/prototypes/games_advisor/`）有哪些按鈕與欄位；載入中、沒有資料、錯誤時各顯示什麼。
5. 哪些角色可以使用；沒有權限時回什麼。

## Answer

2026-11-08 和立倫看草圖定案。草圖：[`prototypes/api-contract.html`](../prototypes/api-contract.html)，用瀏覽器直接開，下方有 6 條導覽可以照順序點。

**1. API**

`POST /api/v1/advisor/messages`，成功回 201。

- 推薦 Agent 只有一個，所以 `advisor` 用單數。送出一則訊息就是新增一筆訊息，符合 §4.3「不是增刪改查的動作，當成新增子資源」。
- 後端不存對話，所以沒有 GET，也沒有列出對話的端點。

請求：

```json
{ "content": "我們 4 個人", "previous_response_id": null }
```

- `content`：去掉前後空白後 1–500 字。
- `previous_response_id`：上一則回應的 `response_id`；新對話給 `null`。

回應：

```json
{
  "response_id": "resp_…",
  "reply": "幫你找到 3 款適合 4 個人、輕鬆聊天的桌遊。",
  "relaxed_constraint": null,
  "recommendations": [
    {
      "game": { "id": "<uuid>", "name": "璀璨寶石", "min_players": 2, "max_players": 4,
                "min_playtime": 30, "max_playtime": 30, "min_age": 10, "weight": 1.8 },
      "reason": "規則簡單、不燒腦，符合你想要的輕鬆路線；心得提到一局節奏很快。",
      "excerpts": [ { "id": "<uuid>", "text": "…", "language": "zh-TW" } ]
    }
  ]
}
```

- `relaxed_constraint`：`playtime`、`age` 或 `null`。整則訊息只有一個值，因為同一則訊息的卡片都來自同一次查詢；怎麼判斷見「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」第 6 點。
- `recommendations`：最多 3 筆，照工具回傳的順序。追問、離題、查無結果時是空陣列。
- 每張卡片分三塊：`game` 由程式從資料庫填，`reason` 由 LLM 寫，`excerpts` 是該款被引用的心得片段，只有 `id`、`text`、`language`（第 7 點）。
- `game` 的欄位名稱跟著桌遊資料表，寫 spec 時一起定；上面的名稱是暫定。

**2. 錯誤**

| 情況 | 狀態碼 | `error.code` | 畫面 |
|---|---|---|---|
| 欄位錯誤（空白、超過 500 字） | 422 | `VALIDATION_ERROR`（框架預設） | 前端先擋；萬一發生，同 503 |
| 未登入（只在 JWT 模式） | 401 | `UNAUTHENTICATED`（現有） | 請先登入 |
| 對話過期或 id 錯（`LLMConversationNotFound`） | 404 | `GAMES_ADVISOR_CONVERSATION_NOT_FOUND` | 清空畫面，顯示「對話已失效，請開始新對話」，剛剛那句放回輸入框 |
| Azure 暫時連不上，LLM 或 embedding 都算（`LLMUnavailable`、`EmbeddingError`） | 503 | `GAMES_ADVISOR_UNAVAILABLE` | 剛剛那句從畫面拿掉、放回輸入框，提示再送一次 |
| 其他程式錯誤（`LLMError` 等） | 500 | `INTERNAL_ERROR`（現有） | 同 503 |
| 網路斷線、後端沒開 | — | `NETWORK_ERROR`（前端產生，現有） | 同 503 |

- LLM 和 embedding 共用一個 503 錯誤碼：前端處理方式一樣。
- 503 不在 §4.3 的清單裡，由立倫向組員提議補進去（AI 不改 AGENTS.md）。

**3. 每種結果回哪個 `response_id`**

| 結果 | 狀態碼 | `response_id` |
|---|---|---|
| 一般回覆：追問、推薦、離題、查無結果 | 201 | 新的 id |
| 固定文字：模型拒答或內容被過濾（`LLMOutputRejected`） | 201 | 請求帶來的舊 id（第一則訊息就是 `null`） |
| 固定文字：推薦全部被程式丟掉 | 201 | 同上 |
| 422、401、503、500、斷線 | 錯誤 | 前端沿用原本的 id，玩家重送就接得上 |
| 404 | 錯誤 | 前端清空，id 回到 `null` |

- 回舊 id 代表這則訊息不算進對話：Agent 不會記得這段失敗的往返，中途的工具呼叫也不會留下沒送回結果的紀錄。固定文字本身就請玩家再說一次。
- 固定文字暫定為「這則訊息我沒辦法回答，請換個說法再試一次。」（拒答）、「這次推薦出了問題，請再說一次你的需求。」（全部丟掉）。
- 回應不標示是不是固定文字，前端照一般回覆顯示。

**4. 不串流**

整則訊息一次回來，等待時顯示「正在找桌遊…」。

- dio 在 Flutter Web 用 XHR，讀不到串流，要另加套件（[dio issue #2254](https://github.com/cfug/dio/issues/2254)）。
- 呼叫工具的那段時間本來就沒有字可以顯示；最終輸出是 JSON，`reply` 在前，邊收邊解析很麻煩；重點是卡片，`reply` 很短。
- 前端的等待上限要比後端的最壞情況長：一則訊息最多呼叫 3 次 LLM（2 次工具＋1 次最終回覆），每次上限 `LLM_TIMEOUT_SECONDS`。
- 沒有採用：用 SSE 串流 `reply`。

**5. 角色**

- 玩家、店家人員、管理員都能用：service 呼叫 `require_role(user, "player", "shop_staff", "admin")`。
- 沒有 403。§7.2 的「沒有權限」情境就是未登入，回 401；只有 `AUTH_MODE=jwt` 會發生，開發模式沒帶標頭會用預設測試玩家。
- 後端不檢查 `response_id` 是誰的（「[對話狀態存在哪裡](05-conversation-state.md)」第 4 點）。

**6. 參考畫面（`frontend/lib/prototypes/games_advisor/`）**

| 元件 | 行為 | `state/` 方法 |
|---|---|---|
| AppBar「開始新對話」 | 清空訊息與 `response_id`，不呼叫 API，不跳確認視窗；沒有內容或送出中時停用 | `startNewConversation()` |
| 空畫面：說明文字＋3 個範例按鈕 | 點範例直接送出（Demo 時少打字） | `sendMessage(content)` |
| 訊息列表 | 玩家與推薦 Agent 的訊息；推薦 Agent 的訊息下方接放寬提示與卡片 | — |
| 放寬提示 | 卡片上方一行「以下放寬了「時長」條件」，不是每張卡片各標一次 | — |
| 推薦卡片 | 繁中名稱；「2–4 人 · 30 分鐘 · 10 歲以上 · 難度 1.8 / 5」；推薦理由；「心得片段（n）」預設摺疊，點開看原文，英文片段旁標「英文」 | — |
| 輸入框＋送出 | 1–500 字並顯示字數；Enter 送出、Shift+Enter 換行；送出中停用 | `sendMessage(content)` |
| 規則問答連結 | 輸入框下方固定一行「想問規則或玩法？到規則問答」；`rules_qa` 還沒有頁面，先留位置 | — |

| 狀態 | 顯示 |
|---|---|
| 載入中 | 推薦 Agent 的位置顯示「正在找桌遊…」，輸入框與按鈕停用 |
| 沒有資料（新對話） | 說明文字＋範例按鈕 |
| 404 | 清空畫面，顯示「對話已失效，請開始新對話」，剛剛那句放回輸入框 |
| 503、500、422、斷線 | 剛剛那句從畫面拿掉、放回輸入框，顯示「推薦 Agent 暫時無法回應，請再送一次」，`response_id` 不變 |
| 401 | 「請先登入再使用推薦 Agent」 |
| 追問、離題、查無結果、固定文字 | 只有文字，沒有卡片 |

- 前端狀態（`messages`、`responseId`、`status`、`draft`、`notice`）和 5 個動作（改輸入框、送出、收到回應、失敗、開始新對話）寫在草圖的第一個 `<script>`，寫 `state/` 時照著改成 Riverpod。
- 前端不把訊息存進瀏覽器，重新整理就是新對話（「對話狀態存在哪裡」第 2 點）。

**7. 出處：只顯示心得片段（更正「推薦理由要寫什麼、要不要附出處」第 3 點）**

- 卡片只顯示被引用的心得片段原文，不顯示文章標題、網站名稱，也不連回原文。API 不回 `title`、`site_name`、`source_url`。
- 心得片段資料表不加 `title`。`source_url`、`site_name`、`language` 照「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」留在資料庫，方便查證。
- 風險：AI 助理提醒，在網頁上顯示他人心得的原文屬於著作權法第 52 條的引用，第 64 條要求明示出處，違反可處罰金（第 96 條）。立倫決定接受這個風險。
- 沒有採用：片段旁加一個「原文 ↗」連結（AI 助理的建議）；完全不顯示片段原文。

**8. 聊天介面不用 DevUI**

立倫提過用 Microsoft Agent Framework 的 DevUI 當聊天介面。DevUI 只能接用 Agent Framework 寫的 Agent，官方定位是開發工具；立倫決定這個階段照 AGENTS.md §5.4，參考畫面用 Flutter 寫。

**術語**：`GLOSSARY.md` 沒有變動。「固定文字」是實作用語，不是領域術語。

**留給其他 ticket 的事**

- 「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」：第 2、3 點的 API 情境都要有 pytest（每種狀態碼、每種結果回哪個 `response_id`、`relaxed_constraint`、卡片只有 `excerpts` 三個欄位）。
- 「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」：`LLM_TIMEOUT_SECONDS` 的值決定前端的等待上限（第 4 點）。
- spec：§7 表格加入第 2、3、5 點的情境；`docs/handoff/games_advisor.md` 照第 6 點寫；`game` 的欄位名稱；503 提議給組員。

## Comments

- 2026-11-07（來自「[對話狀態存在哪裡](05-conversation-state.md)」）：請求帶新訊息與上一輪的 `response_id`，回應帶新的 `response_id`，欄位名稱在這張決定。要定 `response_id` 過期或無效時的錯誤碼；前端顯示「對話已失效，請開始新對話」並清空畫面。後端不存對話，所以沒有列出或讀取對話的端點。
- 2026-11-07（來自「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」）：一則訊息最多推薦 3 款；service 每則訊息最多呼叫 2 次工具；人數不合理時由 LLM 向玩家確認，不回 HTTP 錯誤。推薦結果的格式要讓程式能檢查「只推薦工具回傳的桌遊」（可能和「推薦理由要寫什麼」一起決定）。離題規則：問規則或玩法時請玩家改用規則問答（`rules_qa`），prototype 頁面可以考慮放連結。
- 2026-11-08（來自「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」）：推薦結果是卡片，最多 3 張，照工具回傳的順序排列。每張卡片有：程式從資料庫填的繁中名稱、人數、時長、年齡、難度；程式比對工具呼叫得出的放寬條件（時長或年齡）；LLM 寫的推薦理由（最多 2 句）；被引用的心得片段（完整原文、`title`、`site_name`、`source_url`，顯示成「文章標題 · 網站名稱」連到原文，英文不翻譯）。這張要決定：回應裡卡片與放寬條件的欄位名稱和位置；`reply` 與卡片怎麼串流（LLM 的最終輸出是 JSON，`reply` 在前）；片段要不要摺疊或截斷；`reply` 被換成固定文字時（推薦全部被丟掉）畫面顯示什麼。追問與離題時沒有卡片。
- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：service 要把整合層的例外轉成 API 錯誤，狀態碼和錯誤碼在這張決定。`LLMConversationNotFound`：用 §4.3 的 404，符合「找不到」。`LLMUnavailable`、`EmbeddingError`（包括 `EmbeddingUnavailable`）：都是 5xx，不在 §4.3 的清單裡；建議用 503，要不要補進 §4.3 由立倫向組員提議。`LLMOutputRejected`（內容過濾、模型拒答、輸出被截斷）：不回 HTTP 錯誤，回一則固定文字的訊息。`LLMError`：不攔截，變成 500。也要決定失敗時回哪個 `response_id`：只有拿到最終輸出時才回新的 id；回 HTTP 錯誤時前端沿用原本的 id，玩家重送即可；回固定文字時，建議回請求帶來的原 id，這樣這則訊息不會算進對話，中途的工具呼叫也不會留下沒送回結果的紀錄。
- 2026-11-08 進行中：立倫提到聊天介面可以用 Microsoft Agent Framework 的 DevUI。DevUI 只能接用 Agent Framework 寫的 Agent，官方定位是開發工具。立倫決定這個階段照 AGENTS.md §5.4，參考畫面用 Flutter 寫，不用 DevUI。
