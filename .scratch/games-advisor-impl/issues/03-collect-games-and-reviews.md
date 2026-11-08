# 03：收集桌遊資料與心得

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §5、§8.1、§8.2
MR: 不開 MR，在 10 的 MR 裡結案

## 要做什麼

用 Codex 產生心得管線的兩個輸入檔：`games.json`（15 款桌遊）與 `reviews.json`（心得），都放在 repo 外的團隊資料夾。Codex 只收資料，Claude 只寫提示詞；Claude 不代抓網頁。

## 驗收條件

- [ ] Claude 寫 `games.json` 的 Codex 提示詞，放在 `.scratch/games-advisor/prompts/`，格式照 spec §8.1
- [ ] 確認 `prompts/collect-reviews.md` 的輸出格式符合 spec §8.2，不符合就先改提示詞
- [ ] 立倫用 Codex 產生 `games.json`，手填繁中名稱
- [ ] 立倫用 Codex 產生 `reviews.json`
- [ ] 兩個檔都在 repo 外，沒有進 git
- [ ] 在 10 的分支把本檔的 `Status` 改成 `resolved`；新的提示詞也在那裡 commit
