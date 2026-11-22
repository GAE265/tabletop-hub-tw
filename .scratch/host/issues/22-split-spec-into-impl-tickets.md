# 把 spec 拆成實作 ticket

Type: grilling
Status: resolved
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

## Answer

2026-11-22 立倫確認（五題都照推薦）。實作 ticket 共 10 張，放 [`.scratch/host-impl/issues/`](../../host-impl/issues/)。

1. 切法與張數：一張 ticket 是「一個 AI 對話做得完、測試能自己跑綠」的一塊，不是一個 MR。spec 的 140 行情境每一行都分到一張。

   | 編號 | 做什麼 | 驗收的情境 | 行數 |
   |---|---|---|---:|
   | [01](../../host-impl/issues/01-merge-dev-and-realtime-voice-interface.md) | 接回 `dev`；套件與設定；即時語音的介面與 fake | 無情境行，自己的測試 | 0 |
   | [02](../../host-impl/issues/02-host-content.md) | 主持內容：常數、固定台詞草稿、規則要點、指令文字 | C-01 到 C-05 | 5 |
   | [03](../../host-impl/issues/03-graph-flow-and-voice-commands.md) | 圖之一：換節點、結束、語音指令核對、整局記憶 | F-01 到 F-11、F-13；V-01 到 V-10；C-06 到 C-08；M-01、M-02、M-04、M-05 | 29 |
   | [04](../../host-impl/issues/04-graph-pause-resume-and-chatter.md) | 圖之二：主持暫停、繼續、被打斷的那一段、閒聊 | P-01 到 P-16；F-12；M-03 | 18 |
   | [05](../../host-impl/issues/05-rules-lookup-and-thinking-model.md) | `rules_qa` 只檢索的方法；查規則與思考模型兩個節點 | Q-01 到 Q-05；Q-09 到 Q-13 | 10 |
   | [06](../../host-impl/issues/06-hosting-session-endpoints.md) | 三個一般請求的端點、權限、30 分鐘清除 | A-01 到 A-18；M-08、M-09 | 20 |
   | [07](../../host-impl/issues/07-websocket-and-relay.md) | WebSocket 與轉送：聲音、計時、重連、重送、接話方式 | W-01 到 W-13；K-01 到 K-08；T-01 到 T-05；Q-06 到 Q-08；V-11 到 V-17；M-06、M-07 | 38 |
   | [08](../../host-impl/issues/08-cloud-realtime-voice-provider.md) | 阿里雲的 `cloud` 實作與外部服務測試 | 無情境行，`external` 測試 | 0 |
   | [09](../../host-impl/issues/09-frontend-platform-data-state.md) | 前端：`core/platform/` 四個介面、`data/`、`state/` | U-01 到 U-20 | 20 |
   | [10](../../host-impl/issues/10-prototype-handoff-and-live-checks.md) | 參考畫面、交接說明、流程圖；試聽定稿與手動檢查 | spec 第 15.2 節的手動檢查 | 0 |

   寫 ticket 時和給立倫看的表有三處不同，都是因為那幾行要靠後面的程式才測得到：K-08 從 01 移到 07（要有 `host` 開連線的程式）；M-06、M-07 從 06 移到 07（要連上才交回現況）；F-12 從 03 移到 04（要有暫停）。

2. 順序與相依：接回 `dev` 是 01 的第一步。

   ```
   01 ─► 02 ─► 03 ─► 04 ─┐
    │           ├─► 05 ──┼─► 07 ─► 08 ─► 10
    │           └─► 06 ──┘               ▲
    └─► 09（前端，可以和 02 到 07 同時做）──┘
   ```

3. 誰做：01 到 09 是 `ready-for-agent`。08 用立倫本機 `.env` 的阿里雲金鑰跑外部服務測試，AI 可以直接跑，不用每次問。10 是 `ready-for-human`：AI 先做完參考畫面、交接說明、流程圖，再停下來等立倫試聽、跑手動檢查、手機實測。
4. 動到別人的地方：每張 ticket 有一節「動到別人的地方」。共四處：05 改 `rules_qa`（永傑），05 可能改 `integrations/llm`（瑋鋐），09 改 `frontend/lib/core/platform/`（永傑），10 在 `frontend/lib/app/router.dart` 加一條參考畫面的路由（永傑；這一處是寫 ticket 時才發現的）。PR #68 的說明統一 @ 永傑與瑋鋐。05 開工前先寫好給永傑的群組訊息，由立倫貼。`integrations/realtime_voice/` 的擁有者已定（AGENTS.md 1.13，立倫），不用再問。
5. 每張附什麼：`Status`、`Blocked by`、`Spec`（對應的節）、`MR: #68`、要做什麼、要動的檔案、動到別人的地方、驗收條件（情境編號逐組列出，加檢查）。每張各走一次「先 commit 會失敗的測試，再 commit 功能」。`Status` 在做完那張的最後一個 commit 改成 `resolved`。
6. spec 第 13.1 節留到這張定的檔名：圖是 `graph.py`、轉送是 `relay.py`、主持內容是 `content.py`。

這張結案就到了地圖的 Destination。之後由立倫交給總管派實作 worker 與驗收。

## Comments
- 2026-11-22：開工。前提核對過：「[寫 spec.md](21-write-spec.md)」已結案；地圖標了「已由…更正」的行沒有影響切法；Draft PR #68 已開著；本機看到的 `origin/dev`（`cc8c194`）比 `feature/host` 多 104 個 commit，所以把接回 `dev` 排在第一張的第一步。
- 2026-11-22：「[寫 spec.md](21-write-spec.md)」已結案，這張的相依全部結案。[`spec.md`](../spec.md) 第 13、14 節列了要動的檔案與要改的別人的地方；每張情境表格的編號（F、C、V、P、T、Q、M、K、A、W、U）可以直接當成實作 ticket 的驗收項目。
