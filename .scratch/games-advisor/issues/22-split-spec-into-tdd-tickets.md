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
