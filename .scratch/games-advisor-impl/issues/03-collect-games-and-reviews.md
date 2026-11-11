# 03：收集桌遊資料

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §3.1–§3.3、§5、§8.1
MR: 不開 MR，在 05 的 MR 裡結案

## 要做什麼

用 Codex 產生 `games.json`（15 款桌遊），放在 repo 外的團隊資料夾。收到之後先確認每款都有 spec §8.1 的 12 個欄位、數值都在範圍內，05 建資料表時才不會遇到資料塞不進去的情況。Codex 只收資料，Claude 只寫提示詞；Claude 不代抓網頁。

心得（`reviews.json`）2026-11-11 拆到 [12：收集心得](12-collect-reviews.md)。檔名保留 `and-reviews`，因為已合併的文件連到這個檔名。

桌遊編號不在 `games.json` 裡，等匯入時再問立倫（spec §8.1）。

## 驗收條件

- [ ] Claude 寫 `games.json` 的 Codex 提示詞，放在 `.scratch/games-advisor/prompts/`，格式照 spec §8.1（含 `english_name`、`types`）
- [ ] 提示詞請 Codex 先確認 BGG XML API 有沒有回大類排名（`ranks` 裡 `type="family"`）；抓不到類型的桌遊，`types` 由立倫手填
- [ ] 立倫用 Codex 產生 `games.json`，手填繁中名稱
- [ ] 15 款都符合 spec §8.1 的檢查；兩款 Demo 遊戲（血與刃的白薔薇、阿不思學院）在 BGG 查不到時，`bgg_id` 怎麼處理先和立倫決定，再改 spec §3.1
- [ ] `games.json` 在 repo 外，沒有進 git
- [ ] 在 05 的分支把本檔的 `Status` 改成 `resolved`；新的提示詞也在那裡 commit
