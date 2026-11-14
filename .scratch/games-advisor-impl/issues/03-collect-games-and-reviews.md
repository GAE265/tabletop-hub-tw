# 03：收集桌遊資料

Status: resolved
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §3.1–§3.3、§5、§8.1
MR: 不開 MR，在 05 的 MR [#22](https://github.com/GAE265/tabletop-hub-tw/pull/22) 裡結案

## 要做什麼

用 Codex 產生 `games.json`（16 款桌遊，2026-11-11 從 15 款改定），放在 repo 外的團隊資料夾。收到之後先確認每款都有 spec §8.1 的 12 個欄位、數值都在範圍內，05 建資料表時才不會遇到資料塞不進去的情況。Codex 只收資料，Claude 只寫提示詞；Claude 不代抓網頁。

心得（`reviews.json`）2026-11-11 拆到 [12：收集心得](12-collect-reviews.md)。檔名保留 `and-reviews`，因為已合併的文件連到這個檔名。

桌遊編號不在 `games.json` 裡，等匯入時再問立倫（spec §8.1）。

## 驗收條件

- [x] Claude 寫 `games.json` 的 Codex 提示詞，放在 `.scratch/games-advisor/prompts/`，格式照 spec §8.1（含 `english_name`、`types`）
- [x] 提示詞請 Codex 先確認 BGG XML API 有沒有回大類排名（`ranks` 裡 `type="family"`）；抓不到類型的桌遊，`types` 由立倫手填
- [x] 立倫用 Codex 產生 `games.json`，手填繁中名稱
- [x] 16 款都符合 spec §8.1 的檢查；兩款 Demo 遊戲（血與刃的白薔薇、阿不思學院）的 `bgg_id` 已查到，spec §3.1 已改
- [x] `games.json` 在 repo 外，沒有進 git
- [x] 在 05 的分支把本檔的 `Status` 改成 `resolved`；新的提示詞也在那裡 commit

## Answer

2026-11-11 Codex 交出 `games.json`、`games-report.md`、`check_games.py`（都在 repo 外的團隊資料夾），Claude 依 spec §8.1 核對，立倫決定以下幾點：

1. **名單改成 16 款**，8 個類型各 2 款，取代 06 的 15 款（記在「[收錄哪些桌遊、存哪些欄位](../../games-advisor/issues/06-game-coverage-and-fields.md)」的 Comments）。提示詞的「輸入」已改成這份名單。
2. **Demo 遊戲的 BGG ID**：血與刃的白薔薇 400566、阿不思學院 144734，Codex 用 BGG 搜尋找到唯一結果，立倫核對盒子確認。spec §3.1 已改。
3. **血與刃的白薔薇的 `types`**：BGG 沒有任何大類排名，立倫手填 `["party"]`，理由是機制和阿瓦隆幾乎一樣，阿瓦隆是 `party`。「陣營」不另設類型，用機制（Hidden Roles、Traitor Game、Team-Based Game）表示。
4. **《記憶 44》**查不到台灣繁中版，立倫決定保留，06 補上例外。
5. 格式：`check_games.py` 通過，16 款各 12 個欄位，數值都在 spec §8.1 的範圍內；spec 裡「15 款」的地方（§8.7 的提醒門檻改成 13 款、§15）一起改成 16 款。
6. **繁中名稱**：16 款立倫照盒子全部確認。

和提示詞不同的地方：Codex 沒有用 BGG XML API，而是用瀏覽器讀 BGG 頁面與 `api.geekdo.com`。抽查 3 款的 12 個欄位和 BGG 一致，資料本身照用；之後要重抓時仍照提示詞走 XML API。
