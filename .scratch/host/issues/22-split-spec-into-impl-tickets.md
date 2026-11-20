# 把 spec 拆成實作 ticket

Type: grilling
Status: open
Blocked by: 21
Map: [AI 語音主持](../map.md)

## Question

`spec.md` 寫完後，拆成實作 ticket，放 `.scratch/host-impl/issues/`。格式照 `docs/agents/issue-tracker.md` 的「Implementation tickets after a wayfinder effort」。拆完就到了地圖的 Destination，由立倫交給總管派實作 worker 與驗收。

要決定：

1. 切法與張數。
   - 和 games_advisor 不同的地方：地圖、spec、實作 ticket 與程式都在 `feature/host` 這一個分支、同一支 PR（地圖 Notes）。所以一張實作 ticket 不等於一個 MR。
   - 張數要符合學生專題的規模。games_advisor 第一次提出 42 張，被立倫否決，最後是 10 張。
2. 順序與相依。已知的起點：整合層的介面與 fake、框架骨架。
3. 哪些張可以交給 AI 做（`ready-for-agent`），哪些要立倫親手做或在場（`ready-for-human`）。已知要立倫在場的：
   - 主持人的指令、人設與固定台詞定稿：用真的後端試聽（原「[主持人的人設與台詞](18-host-persona-and-script-lines.md)」的題目）。
   - 用真的模型跑手動檢查。
   - 手機實測（要先有 HTTPS）。
4. 動到別人共用區的 ticket 怎麼標。會碰到的有：
   - `frontend/lib/core/platform/`（永傑）。
   - `rules_qa`（永傑）：只有在「[主持人能查哪些資料、誰能開主持](13-host-tools-and-permissions.md)」決定要它加方法時。
   - `integrations/` 的新資料夾：擁有者照「[寫 spec.md](21-write-spec.md)」的結論。
5. 每張附什麼：spec 對應的段落、要改的檔案、相依的 ticket。

## Comments
