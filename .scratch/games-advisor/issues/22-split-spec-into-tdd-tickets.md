# 把 spec 拆成 TDD 實作 ticket

Type: grilling
Status: open
Blocked by: 20, 21
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

`spec.md` 寫完後，要拆成實作 ticket，每張都能直接開 Draft MR（AGENTS.md §7.2）。要決定：

1. **切法**：一張實作 ticket 對應一個 MR 嗎？限制：一個 MR 只做一件事（§2.6）、一個 MR 最多一個 migration（§4.4）、改共用區要 @ 擁有者（§2.3）。
2. **順序與相依**：已知的起點是「建立 Foundry 與三個部署」（含「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」第 8 點要確認的事），接著是[整合層提案](../integrations-proposal.md)第 10 節的 Azure 驗證。後面的整合層、資料表、匯入指令、心得管線、「查桌遊」、對話 service、API、前端怎麼排。
3. **放在哪裡、用什麼狀態**：本 map 的 ticket 用 `open`、`claimed`、`resolved`；實作 ticket 照 `docs/agents/triage-labels.md` 用 `ready-for-agent`、`ready-for-human` 等。要不要和本 map 的 ticket 放在同一個 `issues/` 資料夾。
4. **整合層的 ticket**：`integrations/llm/`、`integrations/embedding/` 由瑋鋐擁有。先把提案交給瑋鋐、談好誰實作再開票，還是先開成 `needs-info`。OpenSpec 規格 `llm-provider` 的更新（提案第 9 節第 6 點）放在哪一張。
5. **每張附什麼**：spec 裡對應的 §7 表格段落、要改的檔案、相依的 ticket。

## Comments

- 2026-11-08（來自「[spec：桌遊資料與心得管線](20-spec-data-and-review-pipeline.md)」）：前半有 4 張新資料表（spec §3），一個 MR 最多一個 migration，拆法在這張決定。整合層提案不用為心得摘要的測試改動（立倫決定 Q6）。批次指令都在 `app.domains.games_advisor.commands`，7 個子指令各有 §7 表格（spec §8）。
- 2026-11-09（來自「[spec：推薦對話與 API](21-spec-conversation-and-api.md)」）：後半寫在 spec §10–§18，§7 表格分在 §11.8（repository、service）、§12.7（對話 service）、§13.4（router）、§14.2–§14.3（前端 `state/`、`data/`）、§15.5（評估題組）。拆票時要注意：參考畫面的路由改 `frontend/lib/app/router.dart`（永傑擁有，要 @）；`main.py` 要多建一個 embedding provider，`core/config.py` 與 `.env.example` 要加 §4.1 的欄位；整合層誰實作、OpenSpec `llm-provider` 規格更新放哪一張（spec §17）；第一張實作 ticket 在 Azure 驗證提案第 10 節，排在「建立 Foundry 與三個部署」之後；spec §18 的 4 件事由立倫向組員提出，不是實作 ticket。
- 2026-11-09 更正上一則：spec §18 的 4 件事（503 補進 §4.3、ADR 0001、ADR 0002、評估題組的位置）組員已討論同意，兩份 ADR 改成 accepted。剩下一個動作：AGENTS.md §4.3 補上 503，由組員親手修改、以 MR 提出（AI 不改 AGENTS.md）；要不要列成一張 ticket、排在 API 的 MR 之前，在這張決定。
