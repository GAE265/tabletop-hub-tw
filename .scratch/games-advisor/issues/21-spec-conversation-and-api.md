# spec：推薦對話與 API

Type: task
Status: resolved
Blocked by: 20
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

接著「[spec：桌遊資料與心得管線](20-spec-data-and-review-pipeline.md)」寫好的前半，把推薦對話與 API 的決定寫進 `.scratch/games-advisor/spec.md`，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格。資料表與設定欄位沿用前半的總覽，不重寫。

範圍與來源（讀各張的 Answer；Comments 只在 Answer 引用時才讀）：

| 範圍 | 來源 |
|---|---|
| 「查桌遊」工具：參數、enum 每則訊息讀資料庫、SQL 篩條件、RRF 排序、心得片段、向量模型不同時當作沒有向量 | 「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」、「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」 |
| 對話 service：對話規則、三道護欄、放寬條件、離題 | 「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」、[ADR 0002](../../../docs/adr/0002-games-advisor-llm-driven-conversation-flow.md) |
| 最終回覆：structured outputs、推薦理由、丟掉無效的推薦、固定文字 | 「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」 |
| API：`POST /api/v1/advisor/messages`、錯誤碼、`response_id` 規則、沒設定模型時回 503 | 「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」、「[LLM 設定也改成 games_advisor 自己的一組嗎](19-games-advisor-llm-settings.md)」、[ADR 0001](../../../docs/adr/0001-games-advisor-conversation-state-in-azure.md) |
| 前端：`data/`、`state/`、`prototypes/`、交接說明 `docs/handoff/games_advisor.md` | 「API 契約與 prototype 頁面」、`prototypes/api-contract.html` |
| 評估題組指令、`eval_cases.json` | 「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」 |
| 模型、推理強度、逾時、前端等待上限 | 「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」 |
| 整合層 | [整合層提案](../integrations-proposal.md)：引用第 11 節的表格，不重抄 |

規則：

- 較晚的 ticket 會更正較早的，以 map 的 Decisions so far 標示的更正為準。
- 每條規則註明出自哪張 ticket。
- 不重新決定已定案的事。發現衝突或缺漏，寫在本張 Comments 問立倫，不自己選。

完成條件：

- service、router、前端 `state/` 都有 §7 表格。API 端點至少成功、失敗各一個案例（§7.5）；權限照「API 契約與 prototype 頁面」：三種角色都能用、未登入 401。
- service 的表格用假的 repository 與 `FakeLLMProvider`、`FakeEmbeddingProvider` 的腳本寫得出來（§7.5）。
- 立倫看過 spec 的這一半。

## Answer

2026-11-09 完成，立倫看過後半、確認結案。後半寫在 [spec.md](../spec.md) §10–§18。

**spec 後半的內容**

- §10 一則訊息怎麼處理：最多 3 次 respond、2 次查詢；不存對話；每次重送對話規則與工具定義。
- §11「查桌遊」工具 `search_games`：參數與 enum（每則訊息讀資料庫）、參數檢查、SQL 篩條件、排序（負面分數 → RRF → 難度 → 名稱）、心得片段、向量模型不同時當作沒有向量並寫 warning log、回傳給 LLM 的內容；repository 與 service 的 §7 表格。
- §12 對話 service：對話規則的內容、三道護欄、最終回覆 `advisor_reply`、程式檢查、放寬的條件、固定文字與例外對應；§7 表格寫成 `FakeLLMProvider` 的腳本。
- §13 API `POST /api/v1/advisor/messages`：請求與回應（`game` 的 8 個欄位跟著桌遊資料表）、錯誤碼與 `response_id`、權限（三種角色、未登入 401）；router 的 §7 表格。
- §14 前端：`data/`（100 秒上限只設在這個請求）、`state/`（5 個狀態、3 個方法）、參考畫面 `/proto/games_advisor`、交接說明的段落；`state/` 與 `data/` 的 §7 表格。
- §15 評估題組 `eval`：開始前的檢查、`eval_cases.json` 格式、計分與次數、報告；進 CI 的 §7 表格，包括題組代碼都在 `tag_vocabulary.json`。
- §16 模型與逾時、§17 整合層（引用提案第 11 節）、§18 要向組員提議的事（503 補進 §4.3、ADR 0001、ADR 0002、評估題組的位置）。
- 前半寫「（後半）」的地方改成章節號碼。

**寫 spec 時發現的缺漏，立倫的決定**（詳見 Comments）

| 題目 | 決定 |
|---|---|
| Q9 兩次查詢都有結果 | 兩次都算，照查詢先後、再照名次排，最多 3 張 |
| Q10 沒查詢卻附推薦 | 只清掉卡片，`reply` 照用，不換固定文字 |
| Q11 模型不照約定回應 | 當作拒答：固定文字 A、舊 id、記 log |
| Q12 人數以外的參數不合理 | 比照人數，錯誤回給 LLM；回錯誤也算一次工具呼叫 |
| Q13 標籤名稱與定義放哪裡 | `prefer_tags`、`avoid_tags` 的參數說明，每則訊息從資料庫產生 |
| Q14 11 條小細節 | 全部照 AI 助理的預設 |

**留給「[把 spec 拆成 TDD 實作 ticket](22-split-spec-into-tdd-tickets.md)」的事**

- 參考畫面的路由要改 `frontend/lib/app/router.dart`（永傑擁有），MR 要 @ 永傑；交接說明的 MR 加 `needs-ui`。
- 後端啟動時要多建一個 embedding provider（`main.py`），`core/config.py` 與 `.env.example` 要加 §4.1 的欄位。
- 整合層誰實作、OpenSpec `llm-provider` 規格的更新放哪一張（spec §17）。
- 第一張實作 ticket 在 Azure 驗證提案第 10 節，排在「建立 Foundry 與三個部署」之後。
- §18 的 4 件事由立倫向組員提出，不是實作 ticket。

## Comments

- 2026-11-08（來自「[spec：桌遊資料與心得管線](20-spec-data-and-review-pipeline.md)」）：前半已寫進 `spec.md`。要沿用的：`game` 物件的欄位名稱跟著 `games_advisor_games`（spec §3.1）；信心門檻 0.5、每款片段數 2、RRF 的 k 60 是程式常數（spec §4.2，立倫決定 Q1）；出處標記用〔收錄〕〔比對〕這類短名稱（spec 開頭的表）。留給這張寫的：「查桌遊」遇到模型不同的向量當作沒有向量並寫 warning log、評估題組開始前檢查向量模型、評估題組代碼都在 `tag_vocabulary.json` 的 pytest。
- 2026-11-08 後半已寫進 `spec.md`（§10–§18）。寫的時候發現 6 個缺漏，spec 裡標「待確認 Qn」，先寫 AI 助理的建議，等立倫決定：
  - **Q9 一則訊息查了兩次、兩次都有結果時，卡片能從哪一次來**：「推薦理由要寫什麼」第 6 點只說「這則訊息的工具結果」。建議兩次都算，卡片照查詢先後、再照名次排，最多 3 張。另一個做法：只認最後一次有結果的查詢。
  - **Q10 這則訊息沒有查詢、LLM 卻附了推薦**：第 6.1 點說當作空的，第 6.4 點說「至少推薦 1 款、全部被丟掉」要換固定文字，兩條會撞在一起。建議只清掉卡片、`reply` 照用、不換固定文字（6.1 的例子「剛剛第二款適合小孩嗎？」就是要用文字回答）。
  - **Q11 模型不照約定回應**（第 3 次仍要求查詢、要求不存在的工具、一次要求查兩次）：真的 Azure 應該不會發生，fake 做得到。建議當作拒答，回固定文字 A、舊 id，記 log。另一個做法：當作程式錯誤回 500。
  - **Q12 人數以外的參數不合理**（時長 0、難度 6、下限大於上限、代碼不在 enum）：「Agent 怎麼追問」只定了人數。建議比照人數，錯誤回給 LLM；回錯誤也算一次工具呼叫。
  - **Q13 標籤的繁中名稱與定義放哪裡讓 LLM 看到**：enum 只有英文代碼，LLM 要靠名稱與定義把「歡樂一點」對到 `laughter`。建議寫在 `prefer_tags`、`avoid_tags` 的參數說明，每則訊息從資料庫產生。另一個做法：寫進對話規則。
  - **Q14 小細節照 AI 助理的預設寫**：
    1. 名稱：工具 `search_games`、最終回覆的 schema `advisor_reply`、工具回傳的欄位名稱（spec §11.7）。
    2. 排序：同分同名次、下一名跳過（1、2、2、4）；沒有向量的桌遊相似度並列最後；難度範圍含邊界；繁中名稱依 Unicode 碼位排。
    3. `preference_text` 只有空白就當作沒帶；沒帶 `preference_text`、心得摘要向量又不能用時，心得片段回空清單。
    4. 某份清單是空的（例如還沒同步詞彙表），工具定義拿掉對應的參數。
    5. 同一款推薦兩次只留第一筆；`excerpt_ids` 超過 2 個只留前 2 個合法的。
    6. 時長、年齡同時放寬時標 `playtime`；沒有卡片時 `relaxed_constraint` 一律 `null`。
    7. `previous_response_id` 是空字串回 422。
    8. API 的 `weight` 回原值，畫面四捨五入到小數 1 位。
    9. 前端：送出中按「開始新對話」不動作；100 秒上限只設在這個請求，寫在 `games_advisor/data/`，不改 `core/api`。
    10. 評估題組：外層 `{"cases": [...]}`、Demo 題標 `"demo": true`、排除清單寫 `exclude_bgg_ids`、`tool_args` 寫 `null` 代表必須沒帶；每個項目 1 分，「未執行」的輪次算沒通過；該輪拿到 503、500 或固定文字算不符合；`--repeat N` 只影響非 Demo 題；報告路徑已存在就拒絕；結束碼 0 跑完、1 拒絕執行。
    11. 評估題組開始前：只有模型不同才拒絕，沒有向量的桌遊只提醒。
- 2026-11-09 立倫決定 Q9–Q13，全部照建議（已寫進 spec，標記改成〔Qn〕）：
  - Q9：兩次查詢都算，卡片照查詢先後、再照名次排，最多 3 張。
  - Q10：沒有查詢卻附推薦時，只清掉卡片，`reply` 照用，不換固定文字。
  - Q11：模型不照約定回應，當作拒答：固定文字 A、舊 id、記 log。
  - Q12：人數以外的參數不合理，比照人數把錯誤回給 LLM；回錯誤也算一次工具呼叫。
  - Q13：標籤的繁中名稱與定義寫在 `prefer_tags`、`avoid_tags` 的參數說明，每則訊息從資料庫產生。
  - Q14：立倫要先看過 11 條再決定。
- 2026-11-09 立倫確認 Q14 的 11 條小細節全部照 AI 助理的預設（已寫進 spec，標記改成〔Q14〕）。
- 2026-11-09 結案後更正：spec §18 的 4 件事組員已討論同意，§18 改名「組員已同意的事」，ADR 0001、0002 改成 accepted。剩下 AGENTS.md §4.3 補 503，由組員親手修改。
