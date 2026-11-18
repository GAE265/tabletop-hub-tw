# Tasks

> 一個 MR（純前端）。先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開；AI 只產出 MR 說明，存在 `docs/mr_info/<分支名稱>.md`。不修改 `AGENTS.md`、`CLAUDE.md`、後端程式、`booking/` 與 `groups/` 的 `data/`、`state/`。

## 1. 前置確認

- [x] 1.1 永傑確認情境表格、程式位置（design.md Decision 1）與檔案清單，驗證：永傑回覆確認
  - 註記：2026-11-18 永傑同意照建議做（程式放在 `lib/app/home/`）。
- [ ] 1.2 把情境表格給一位組員看過（7.2），驗證：至少一位組員確認
- [ ] 1.3 把 design.md 的 Open Questions 2（後端缺口）告知瑋鋐，驗證：已在群組提出（是否處理由組員決定，不影響本 change）

## 2. 測試（先寫、先失敗）

- [x] 2.1 `test/app/home/upcoming_state_test.dart`：合併排序、只列即將到來（已取消／已完成／已開始的訂位與揪團排除、只列 member 與 waitlisted）、最多 5 筆、店家名稱對應、403 視為沒有訂位、其他錯誤進入錯誤狀態、重試、切換身分重新載入，驗證：測試存在且失敗
- [x] 2.2 `test/app/home/home_page_test.dart`：首頁內容、三種角色相同、四張入口卡片導頁、登入提示、手機兩欄與桌機一列、行程列內容與狀態文字（已確認／招募中／已額滿／候補中）、點行程導頁、載入中、空狀態與兩個按鈕、錯誤與重試且入口卡片可點，驗證：測試存在且失敗
- [x] 2.3 `test/app/navigation_test.dart`：手機在底部、桌機在頂部、選取規則（`/booking/mine`、`/rules/1`、`/groups`、`/health`、`/proto/...`）、點項目導頁、每個項目只出現一次，驗證：測試存在且失敗
- [x] 2.4 修改 `test/app/router_test.dart`：「首頁是套主題的正式 health 頁面」改成「`/` 是首頁」與「`/health` 是 health 頁面」（路由需求變動，MR 說明寫理由），驗證：測試存在且失敗
- [x] 2.5 提交測試到功能分支，驗證：commit 只含測試

## 3. 實作

- [x] 3.1 `app/home/state/upcoming_state.dart`，驗證：2.1 全部通過
- [x] 3.2 `app/navigation.dart`、修改 `app/shell.dart`（刪除 `_TemporaryNav`），驗證：2.3 全部通過
- [x] 3.3 `app/home/pages/home_page.dart`、`app/home/pages/widgets/home_widgets.dart`；若需要新的主題 token（例如入口卡片的圖示底色），加在 `app/theme/`，驗證：2.2 全部通過
  - 註記：`AppSizes` 新增 `brandMark`、`entryIconBox`、`entryCardMinWidth`、`dateBadge`；顏色沿用既有的 `AppColors`。
- [x] 3.4 修改 `app/router.dart`（`/` → `HomePage`、`/health` → `HealthPage`），驗證：2.4 與既有 `router_test.dart` 全部通過
- [x] 3.5 grep 確認 `app/home/` 與 `navigation.dart` 沒有寫死的顏色、字級、間距，驗證：沒有結果

## 4. 自我檢查與 MR

- [x] 4.1 在 `frontend/` 跑 `flutter analyze`、`flutter test`（Flutter 3.41.4），驗證：全部通過
  - 註記：analyze 沒有問題，338 個測試全部通過。
- [ ] 4.2 本機手動走過：手機與桌機寬度、player／shop_staff／admin 三種身分、有行程與沒有行程、關掉後端看錯誤與重試，驗證：符合設計稿
- [ ] 4.3 產出 MR 說明 `docs/mr_info/feature/home-page.md`（含情境表格與對應測試、修改既有測試的理由），驗證：檔案存在、未 commit
- [x] 4.4 更新 `docs/handoff/home.md` 第 4、6 節（資料來源與程式位置的結論），驗證：內容與 design.md 一致

## Workflow follow-up

- MR 合併後執行 `/opsx:archive`。
