# Tasks

> 第 2 階段（design.md D7，兩個 MR）。先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節）；AI 只產出 MR 說明存到 `docs/mr_info/`，情境表格依類別分組並標示對應的測試（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置

- [x] 1.1 永傑確認情境表格與 design.md 的待決問題（2026-11-21 全部確認，另加 dry-run 的 `--apply`、寫入後涵蓋檢查、未被要求修改的欄位、目標不明確、動作判斷依據、MR 1 的畫質檢查；見 design.md「已決定」）
- [x] 1.3 兩個 MR 都先在本機做完、測完，不 push（2026-11-21 永傑指示）
- [x] 1.2 第 1 階段的前置項目帶進來：進度條最後才疊上去（`add-rules-video-maker` 的 Workflow follow-up）

## 2. MR 1：進度條最後才疊上去（分支 `feature/integrations-video-progress-overlay`）

- [x] 2.1 第一個 commit：本 change 的 OpenSpec 文件
- [x] 2.2 撰寫測試：段影片不含進度條、靜態圖仍有、`content_hash` 不受全片長度影響、旁白長度改變只重做那一段（依 7.5 說明第 1 階段測試的預期改變），驗證：測試存在且失敗
- [x] 2.3 撰寫 external 測試：成品第 t 秒的進度條填滿比例；疊加前與成品的 SSIM（不含進度條），驗證：`uv run pytest` 不執行它
- [x] 2.4 實作：`Renderer.render(progress=…)`、進度條影片、ffmpeg overlay、`content_hash` 拿掉 progress，驗證：2.2 通過、本機 external 通過
- [x] 2.5 用《血與刃》步驟三重新輸出，驗證：**交給永傑看成品**（進度條正常、音軌與畫面一樣長）
  - 本機結果（2026-11-21）：27.9 秒、1920×1080、30 fps，音軌與畫面一樣長；進度條在 25%／50%／75% 填滿 0.251／0.501／0.750；與第 1 階段成品比 SSIM 0.9992、PSNR 54.7 dB；副本只改 s2 標題時只重新編碼 1 段。永傑看過成品，合格（2026-11-21）
- [ ] 2.6 自我檢查與 MR 說明，驗證：全部通過、CI 全綠

## 3. MR 2：修改流程（分支 `feature/rules_qa-video-revision`）

- [x] 3.1 撰寫測試（`FakeLLMProvider`）：只取代列出的段、不能改 key 或增刪段、檢查不通過改寫一次、備份、`--dry-run` 與 `--apply`、未被要求修改的欄位、超過 2 段的提醒、目標不明確與 `--segment`、修改紀錄與 `changed`、`render` 後更新狀態、超出能力（LLM 回報與五種以外的動作）、`--choose`、寫入後的涵蓋檢查警告、LLM 無法使用，驗證：測試存在且失敗
- [x] 3.2 實作 `video_revision.py`、指示與 schema、`video_commands revise`，驗證：3.1 通過
- [x] 3.3 用《血與刃》步驟三實際修改：至少一個一般修改（例如「情況二的紅框改成金框」）、一個超出能力的要求，驗證：**交給永傑看修改結果、只重做的段、修改紀錄與需求紀錄**
  - 本機結果（2026-11-21，副本 `.local/rules_video_revise/`）：「情況二的紅框改成金框」dry-run → apply 只改 s2 的 highlights，render 只重新編碼 1 段；「白薔薇旋轉著飛進白薔薇區」判為超出能力、記到 requests.json，`--choose 1` 套用成功。驗收中發現兩個問題（segment_json 省略 segment_key、替代做法要在產生時檢查），已先寫測試再修正。永傑看過結果，合格（2026-11-21）
- [x] 3.5 補強（2026-11-21 永傑要求）：沒有實際變動的替代做法視為無效（改寫一次，仍無效就不列出）；用真的 LLM 驗收 (a) 目標不明確列出候選段、(b) 旁白改短時涵蓋檢查顯示警告、(c) 一次 3 段時提醒確認，驗證：測試先行、三項結果都符合
- [ ] 3.4 自我檢查與 MR 說明，驗證：全部通過、CI 全綠

## Workflow follow-up

- 第 3 階段的輸入：`revisions/requests.json` 累積的「超出能力」需求；`add-rules-video-script` 記錄的兩個畫面問題（紅叉留在空位、紅色標籤疊在側欄文字上）。
- 兩個 MR 合併後，與第 1 階段的 change 一起歸檔（見本機分支 `docs/archive-add-rules-video-maker`）。
