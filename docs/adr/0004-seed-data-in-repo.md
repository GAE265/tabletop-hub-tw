---
status: accepted
---

# 共用桌遊與推薦 Agent 的資料放進 repo，由開發用 seed 寫入

組員 clone repo、跑完 `uv run alembic upgrade head` 與 `uv run python -m app.dev.seed` 之後，`games` 與推薦 Agent 的資料表還是空的：共用桌遊資料要另外到團隊雲端資料夾 GAE265G5 下載匯出檔再執行 `sync-games`，推薦 Agent 的資料（標籤、心得摘要、心得片段與向量）則完全沒有取得的管道。2026-11-19 立倫決定：只要他的本機資料庫查得到實體資料，組員就該用 seed 取得一樣的資料，資料檔一律放進 repo。

所以共用桌遊的匯出檔（`games-export.json`）與推薦 Agent 4 張表的資料（`games_advisor_data.sql`）放在 `backend/app/dev/seed_data/`，開發用 seed 多一個桌遊步驟把它們寫進資料庫。跑一次 seed，下面 7 張表就和立倫的本機資料庫相同：`games`（16 款）、`game_genres`、`genres`（migration 寫入）、`games_advisor_tags`、`games_advisor_game_tags`、`games_advisor_review_summaries`、`games_advisor_review_excerpts`。

同一天稍早，PR #66 已先把同一份匯出檔放進 `backend/app/dev/games-export.json`，並在 README 加上手動執行 `sync-games` 的步驟。這個決定把它收進 `seed_data/`、改由 seed 讀取：`backend/app/dev/games-export.json` 刪除（兩份內容相同），README 不再需要 `sync-games` 那一步；PR #66 加的 `seed_shop` 步驟保留。

這推翻了 [ADR 0003](0003-shared-games-table.md) 的這幾句，其餘照舊：

- 「`games.json` 與匯出檔都不進 repo」「GAE265G5 的匯出檔是唯一的備份」「GAE265G5 只放最新的一份匯出檔，每次覆蓋」：匯出檔改放 repo，repo 就是備份，GAE265G5 不再放匯出檔。`games.json`（Codex 整理的臨時資料）仍然不進 repo。
- 「其他組員下載後執行同步」：組員改成跑 seed，不用自己執行 `sync-games`。
- 「只有 games_advisor 的兩個指令會寫入」：多了開發用 seed。它呼叫 `sync-games` 背後的同一個 service，沒有另一份同步邏輯。
- 「推薦用的資料（心得摘要、標籤、心得片段）留在 games_advisor 自己的表，不同步」：資料仍在 games_advisor 自己的表，但現在也由 seed 寫入。

同步的規則沒有變：資料庫的桌遊和匯出檔完全一樣，匯出檔沒有的桌遊會刪掉；編號給出去就不改；`import-games` 仍然只有立倫在空的資料庫執行一次。

## Considered Options

- **維持 ADR 0003：匯出檔放 GAE265G5，推薦資料用交接包另外給**：repo 不含心得原文，但每位組員都要多做下載、同步、匯入 SQL 三個手動步驟，漏做就看不到推薦結果，資料更新時也要再做一次。
- **repo 只放共用桌遊的匯出檔，推薦資料仍另外給**：`games` 有資料了，但推薦 Agent 還是空的，組員跑不出推薦。
- **放 reviews.json，讓組員自己跑心得摘要、心得片段、上標籤的指令**：repo 不放向量，但每個人都要有 LLM 與 embedding 的金鑰、花費 token，而且每個人產生的摘要與標籤都不一樣，Demo 與評估結果對不起來。
- **把資料寫進 migration**：AGENTS.md §4.4 規定已合併的 migration 不得修改，資料每更新一次就要多一個 migration；測試帳號也因為同樣的理由不寫進 migration。

## Consequences

- **repo 是公開的，現在包含第三方的心得原文。** `games_advisor_review_excerpts` 有 128 段心得原文（來自 62 個網站的 80 篇文章），每段都帶來源網址與網站名稱；`games_advisor_review_summaries` 是 LLM 依這些心得寫的摘要。立倫 2026-11-19 確認知道這一點。這不是 AGENTS.md §2 禁止提交的規則書全文或合作店家資料；規則書原文（`games_manual`、`rules_qa_chunks`）仍然不進 repo，也不在這次的範圍。
- **seed 會覆蓋這 7 張表。** 每次跑 seed，`games`、`game_genres` 與 4 張 `games_advisor_` 表都會變成和資料檔一樣；組員自己在本機新增的桌遊、自己跑指令產生的標籤或心得資料都會被換掉。測試一律用寫在測試程式裡的假資料。
- **桌遊步驟自成一個交易。** 同步桌遊、清空 4 張 `games_advisor_` 表、寫入推薦資料要嘛全部成功，要嘛全部退回。失敗時 seed 印出原因、結束碼是 1，但測試帳號、測試店家與教學影片照常建立。
- **只寫自己的表。** 桌遊步驟只寫 `games`、`game_genres` 與 4 張 `games_advisor_` 表；清空時不加 CASCADE。2026-11-19 查證（資料表版本 0012）：沒有其他 domain 的表以外鍵指向這 4 張 `games_advisor_` 表。
- **`group_games` 和 ADR 0003 不一致，還沒解決。** ADR 0003 規定其他 domain 的表參照 `games.id` 時不可以「桌遊刪掉就跟著刪」，但 `group_games.game_id` 設定成跟著刪（groups 的 model 註解寫明是刻意的：同步時只刪掉這筆對應，揪團保留）。後果：組員本機新增的桌遊如果被揪團選用，seed 不會擋下，會連那筆對應一起刪。`games_manual`、`rules_qa_videos`、`rules_qa_chunks`、`matches` 沒有這個設定，會照 ADR 0003 擋下。1–16 號是原地更新，不受影響。要不要改 `group_games`，由 groups 主責（永傑）與立倫決定。
- **資料更新走 MR。** 立倫的本機資料庫仍是正本。資料有變（補 `result_type`、重跑心得管線、新增桌遊）時，立倫重新產生兩個資料檔、發 MR；組員拉下 `dev` 後重跑 seed。做法寫在 `backend/app/dev/seed_data/README.md`。
- **推薦資料檔約 2.9 MB**，幾乎都是向量。每更新一次，git 歷史就多一份。
- **向量固定是 text-embedding-3-large、1536 維。** `GAMES_ADVISOR_EMBEDDING_DIM` 不是 1536 的資料庫寫不進去，seed 會印出原因。
- **seed 只在 `AUTH_MODE=dev` 執行。** 部署到 Azure 的正式資料庫時，共用桌遊仍照 ADR 0003 由立倫執行 `sync-games`（匯出檔改從 repo 拿）；推薦 Agent 的資料怎麼放進正式資料庫，還沒決定。
- 匯出檔不進 repo 的那套流程（README 的「同步共用桌遊資料」、GAE265G5 的匯出檔）不再需要。`import-games`、`export-games` 印出的提示與 games_advisor 的規格還寫著「把匯出檔放進 GAE265G5」，這次沒有改，要另外更新。
