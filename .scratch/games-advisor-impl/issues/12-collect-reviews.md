# 12：收集心得

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §5、§8.2
MR: 不開 MR，在 10 的 MR 裡結案

## 要做什麼

用 Codex 產生心得管線的輸入檔 `reviews.json`，放在和 `games.json` 同一個 repo 外的團隊資料夾。2026-11-11 從 03 拆出來：05 只需要桌遊資料，不用等心得收完。Codex 只收資料，Claude 只寫提示詞；Claude 不代抓網頁。

Codex 收心得時會讀 `games.json` 的 `bgg_id`、`name`、`english_name`，所以先做 03 比較方便，但沒有硬性阻擋。

## 驗收條件

- [ ] 確認 `prompts/collect-reviews.md` 的輸出格式符合 spec §8.2，不符合就先改提示詞
- [ ] 立倫用 Codex 產生 `reviews.json`
- [ ] `reviews.json` 在 repo 外，沒有進 git
- [ ] 在 10 的分支把本檔的 `Status` 改成 `resolved`；改過的提示詞也在那裡 commit
