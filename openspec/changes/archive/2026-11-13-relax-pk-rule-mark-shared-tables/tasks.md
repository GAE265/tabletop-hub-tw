# Tasks

## 1. 更新 database-baseline 規格

- [x] 1.1 直接編輯 `openspec/specs/database-baseline/spec.md` 的 Purpose：把「兩張共用表」改為說明 `auth_users` 與 `booking_shops` 都是 AGENTS.md 第 3 節列出的共用資料表；驗證：Purpose 不再出現「兩張共用表」，且明確寫出兩張表名。
- [x] 1.2 確認沒有修改 `AGENTS.md`、`docs/review-guide.md`、`openspec/changes/archive/`、`backend/`；驗證：`git diff --stat` 的檔案清單只有本 change 目錄與 `openspec/specs/database-baseline/spec.md`（AGENTS.md 與 review-guide.md 的差異是使用者自己放入的，另外 commit）。
- [x] 1.3 執行 `openspec validate relax-pk-rule-mark-shared-tables --strict`；驗證：指令通過，沒有錯誤與警告。

## Workflow follow-up

- 測試案例：不適用，只改文件與規格，行為不變。
- 依使用者指示分兩個 commit：先 `docs: AGENTS.md 1.8 調整資料庫規則與共用資料表`（含 docs/review-guide.md，由使用者提供），再 `docs(openspec): 放寬主鍵規則並標示共用資料表`。
- 執行 `/opsx:archive` 套用 delta 到主 spec，之後再跑一次 `openspec validate --strict`。
- 開 Draft MR 到 `dev`，MR 說明的情境表格寫「不適用：只改文件與規格，行為不變」。
