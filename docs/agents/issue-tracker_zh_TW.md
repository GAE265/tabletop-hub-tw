# Issue tracker：Local Markdown

> 本檔是 [`issue-tracker.md`](./issue-tracker.md) 的繁體中文翻譯，給組員閱讀。mattpocock skills 的 agent 讀英文版；兩者內容不一致時，以英文版為準。

本 repo 的 issue 與 spec 以 markdown 檔存在 `.scratch/`。

## 慣例

- 一個功能一個資料夾：`.scratch/<feature-slug>/`
- spec 是 `.scratch/<feature-slug>/spec.md`
- 實作用的 issue 一張 ticket 一個檔：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，從 `01` 開始編號；不要把所有 ticket 合成一個檔
- triage 狀態寫在每個 issue 檔開頭附近的 `Status:` 行（角色字串見 [`triage-labels_zh_TW.md`](./triage-labels_zh_TW.md)，英文版為 `triage-labels.md`）
- 留言與討論紀錄附加在檔案最後的 `## Comments` 標題下

## 當 skill 說「publish to the issue tracker」（發佈到 issue tracker）

在 `.scratch/<feature-slug>/` 底下新增檔案（資料夾不存在就先建立）。

## 當 skill 說「fetch the relevant ticket」（取得相關 ticket）

讀取指定路徑的檔案。使用者通常會直接給路徑或 issue 編號。

## Wayfinding 操作

給 `/wayfinder` 使用。**map** 是總覽檔，每張 ticket 各自是它底下的一個 **child** 檔。

- **Map**：`.scratch/<effort>/map.md`（即 Notes／Decisions-so-far／Fog 這些段落的內文）
- **Child ticket**：`.scratch/<effort>/issues/NN-<slug>.md`，從 `01` 開始編號，內文寫要回答的問題。`Type:` 行記錄 ticket 類型（`research`／`prototype`／`grilling`／`task`）；`Status:` 行記錄 `claimed`／`resolved`
- **Blocking**：在檔案開頭附近寫一行 `Blocked by: NN, NN`。列出的檔案全部是 `resolved` 時，這張 ticket 才不再被擋住
- **Frontier**（目前可以接手的 ticket）：掃描 `.scratch/<effort>/issues/`，找出還沒結案、沒被擋住、也沒人認領的檔案；編號最小的優先
- **Claim**（認領）：動工前先設定 `Status: claimed` 並存檔
- **Resolve**（結案）：在檔案最後加上 `## Answer` 標題並寫入答案，設定 `Status: resolved`，再到 `map.md` 的 Decisions-so-far 補上一筆 context pointer（摘要加連結）
