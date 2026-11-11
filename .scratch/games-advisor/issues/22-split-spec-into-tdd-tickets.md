# 把 spec 拆成 TDD 實作 ticket

Type: grilling
Status: resolved
Blocked by: 20, 21
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

`spec.md` 寫完後，要拆成實作 ticket，每張都能直接開 Draft MR（AGENTS.md §7.2）。要決定：

1. **切法**：一張實作 ticket 對應一個 MR 嗎？限制：一個 MR 只做一件事（§2.6）、一個 MR 最多一個 migration（§4.4）、改共用區要 @ 擁有者（§2.3）。
2. **順序與相依**：已知的起點是「建立 Foundry 與三個部署」（含「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」第 8 點要確認的事），接著是[整合層提案](../integrations-proposal.md)第 10 節的 Azure 驗證。後面的整合層、資料表、匯入指令、心得管線、「查桌遊」、對話 service、API、前端怎麼排。
3. **放在哪裡、用什麼狀態**：本 map 的 ticket 用 `open`、`claimed`、`resolved`；實作 ticket 照 `docs/agents/triage-labels.md` 用 `ready-for-agent`、`ready-for-human` 等。要不要和本 map 的 ticket 放在同一個 `issues/` 資料夾。
4. **整合層的 ticket**：`integrations/llm/`、`integrations/embedding/` 由瑋鋐擁有。先把提案交給瑋鋐、談好誰實作再開票，還是先開成 `needs-info`。OpenSpec 規格 `llm-provider` 的更新（提案第 9 節第 6 點）放在哪一張。
5. **每張附什麼**：spec 裡對應的 §7 表格段落、要改的檔案、相依的 ticket。

## Answer

2026-11-09 與立倫 grilling 定案，分兩段對話。第一段提出 9 個 MR、42 張 ticket，立倫否決，要求符合學生專題的規模；第二段收斂成 10 張。實作 ticket 在 [`.scratch/games-advisor-impl/issues/`](../../games-advisor-impl/issues/)。

**10 張實作 ticket**

| # | ticket | 狀態 | 要等 |
|---|---|---|---|
| 01 | AGENTS.md §4.3 補上 503（立倫親手改） | ready-for-human | — |
| 02 | 建立 Foundry 並在 Azure 驗證（提案第 10 節） | ready-for-human | — |
| 03 | 收集桌遊資料與心得（Codex） | ready-for-human | — |
| 04 | 整合層介面與 fake | ready-for-agent | — |
| 05 | 資料表（4 張表、1 個 migration） | ready-for-agent | 04 |
| 06 | 心得管線（7 個批次指令） | ready-for-agent | 05 |
| 07 | 推薦對話與 API | ready-for-agent | 01、05 |
| 08 | 雲端實作 | ready-for-agent | 02、04 |
| 09 | 前端與交接說明 | ready-for-agent | —（截圖除外） |
| 10 | 評估題組與詞彙表 | ready-for-human | 03、06、07、08 |

```
04 → 05 → 06 ─┐
        └→ 07 ┼→ 10
01 ───→ 07    │
02、04 → 08 ──┤
03 ───────────┘
09 隨時可以寫
```

**決定**

1. **切法**：照 spec 的段落切，不做垂直切片。一張 ticket 對應一個 MR；不產生 MR 的只有 02、03。程式 MR 共 7 個（04–10），另有 01 的 AGENTS.md MR 與文件 MR。
2. **資料表**：4 張表放同一個 migration，單獨一個 MR（05）。repository 函式跟著用到它的指令或 service 一起寫。
3. **整合層**：組內慣例是「需要的人先做，再請擁有者審」，由立倫實作，MR @ 瑋鋐，不開 `needs-info`。介面與 fake（04）和雲端實作（08）分開；提案 §11.1 中需要雲端實作的 4 列放 08。OpenSpec `llm-provider` 規格在 08 更新：08 合併後，「只支援 fake」「cloud 尚未實作」兩條才不成立，一次改完；04 合併到 08 合併之間，規格暫時少列兩個方法。
4. **503**：開成 01，立倫親手改 AGENTS.md 並開 MR，排在 07 之前。
5. **真資料**：只開兩張：03 收資料、10 跑資料並定案。Foundry 與 Azure 驗證合成 02，建議最先做，因為走備案（「交卷」工具）會改到 04 的介面與 07 的 service。
6. **評估題組指令放 10**：`eval` 是 `commands` 的子指令，`commands` 在 06 建立；放 07 的話，07 要等 06 合併（AGENTS.md §8.1），兩者就不能同時做。10 本來就要等 06、07，`eval` 也要有真資料才跑得起來。
7. **交接說明的截圖**：09 的程式隨時可以寫，`Blocked by` 寫「無」。截圖是最後一個勾選項目，要等 06、07、08 合併、匯入真的桌遊並產生心得片段；不用等 10 的詞彙表（詞彙表是空的時，工具會拿掉標籤參數，spec §11.1）。
8. **ticket 的內容**：照 `to-tickets` 的範本：標題、`Status:`、`Blocked by:`、`Spec:`、`MR:`、1–3 句「要做什麼」、勾選項目。驗收條件是指定段落的 §7 表格每一列都有測試而且通過、AGENTS.md §2 第 7 點的檢查通過。不列檔案，不複製表格。「開 Draft MR」不另外開 ticket，改成每張 MR ticket 的第一個勾選項目。
9. **位置與狀態**：放 `.scratch/games-advisor-impl/issues/`，從 01 開始編號。狀態只有 `ready-for-agent`／`ready-for-human` 與 `resolved`，不記錄「進行中」。有 MR 的 ticket 在自己的 MR 裡、合併前最後一個 commit 改成 `resolved`；02 在 08 的 MR 結案，03 在 10 的 MR 結案。慣例寫進 `docs/agents/issue-tracker.md` 與 `issue-tracker_zh_TW.md`。
10. **文件 MR 先合併**：`origin/dev` 底下還沒有 `.scratch/games-advisor/`，從 dev 開出的程式分支看不到 spec。這支分支改名為 `docs/games_advisor-spec`，開成文件 MR，合併後才開始 01–10。push 與開 MR 由立倫做。

**和第一段的差別**

- 「開 Draft MR」從 9 張 ticket 改成勾選項目（立倫原本同意每個 MR 的第一張 ticket 是開 Draft MR）。
- 7 個批次指令不再各開一張，全部放在 06。
- 真資料的工作從 8 張縮成 03、10 兩張。
- 整合層、「查桌遊」、前端不再依程式的層拆開。
- 第一段沒回答的「狀態跟著哪個分支 commit」與「截圖要等什麼」，見上面第 9、7 點。

## Comments

- 2026-11-08（來自「[spec：桌遊資料與心得管線](20-spec-data-and-review-pipeline.md)」）：前半有 4 張新資料表（spec §3），一個 MR 最多一個 migration，拆法在這張決定。整合層提案不用為心得摘要的測試改動（立倫決定 Q6）。批次指令都在 `app.domains.games_advisor.commands`，7 個子指令各有 §7 表格（spec §8）。
- 2026-11-09（來自「[spec：推薦對話與 API](21-spec-conversation-and-api.md)」）：後半寫在 spec §10–§18，§7 表格分在 §11.8（repository、service）、§12.7（對話 service）、§13.4（router）、§14.2–§14.3（前端 `state/`、`data/`）、§15.5（評估題組）。拆票時要注意：參考畫面的路由改 `frontend/lib/app/router.dart`（永傑擁有，要 @）；`main.py` 要多建一個 embedding provider，`core/config.py` 與 `.env.example` 要加 §4.1 的欄位；整合層誰實作、OpenSpec `llm-provider` 規格更新放哪一張（spec §17）；第一張實作 ticket 在 Azure 驗證提案第 10 節，排在「建立 Foundry 與三個部署」之後；spec §18 的 4 件事由立倫向組員提出，不是實作 ticket。
- 2026-11-09 更正上一則：spec §18 的 4 件事（503 補進 §4.3、ADR 0001、ADR 0002、評估題組的位置）組員已討論同意，兩份 ADR 改成 accepted。剩下一個動作：AGENTS.md §4.3 補上 503，由組員親手修改、以 MR 提出（AI 不改 AGENTS.md）；要不要列成一張 ticket、排在 API 的 MR 之前，在這張決定。
- 2026-11-11 資料表改版與 ticket 順序調整（立倫 grilling 定案，spec 標〔改表〕）：
  - **順序**：欄位先定案 → 03 收桌遊資料 → 05 建表。03 拆成兩張：03 只做 `games.json`、在 05 的 MR 結案；新開 12 做 `reviews.json`、在 10 的 MR 結案。05 的 Blocked by 改成 03、04；10 改成 03、06、07、08、12。不拆的話 05 等 03、03 等 10、10 又等 05，會卡成死結。
  - **共用表**：`games`、`game_types`（8 個類型）、`game_game_types` 給所有 domain 直接查詢，表名不用 domain 開頭，`games.id` 是立倫指定的 "1"、"2"…… 字串編號（AGENTS.md §4.2、§4.4 的例外，見 ADR 0003）。不開 ticket 改 AGENTS.md，理由寫在 05 的 MR。負責人立倫，程式在 `backend/app/core/games/`。
  - **編號**：給出去就不改、不重複使用；`games.json` 不帶編號，匯入時問立倫，產生臨時的編號對應檔。
  - **欄位**：`english_name` 取代 `original_name`；`categories`、`mechanics` 不加前綴；`bgg_id` 保留；一款可以有多個類型，類型由 Codex 從 BGG 抓，抓不到的立倫手填。
  - **用詞**：8 大類叫「類型」（`type`），BGG 細分類叫「類別」（`categories`），「種類」不用。
  - **心得摘要**搬到 `games_advisor_review_summaries`；標籤、心得片段的 `game_id` 改參照 `games.id`。
  - **標籤**：立倫給的 35 個關鍵字寫進歸納詞彙表的提示詞，當作優先的候選詞；和既有規則衝突的詞在審核時照規則處理。
  - **不在這次**：推薦用不用類型篩選，之後再談。
