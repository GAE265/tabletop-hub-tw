# Proposal

## Why

規則書匯入（`rules_ingest`）目前只有參考畫面 `/proto/rules-ingest`，要開 `SHOW_PROTOTYPES` 才看得到，正式部署進不去，管理員沒辦法實際匯入規則書。瑋鋐已在 `docs/handoff/rules_ingest.md` 交接，由永傑做正式頁面。

## What Changes

- 新增正式頁面 `/rules-ingest`（`frontend/lib/domains/rules_ingest/pages/rules_ingest_page.dart`），直接使用既有的 `state/`，行為與參考畫面相同，套用主題並支援 RWD：
  - 選桌遊（可輸入過濾）、起始頁碼。
  - 選圖片：縮圖、匯入成第幾頁、拖曳調整順序、移除。
  - 匯入：進度與每一頁的結果，完成後自動讀回。
  - 已入庫頁面：OCR 實作提示（fake／cloud）、每一頁的內容。
- 導覽列新增「匯入」，**只有管理員看得到**；頁面也只開放給管理員，其他人看到「只有管理員可以匯入規則書」（使用者決定，後端仍允許店家人員）。
- 刪除參考畫面 `/proto/rules-ingest` 與 `RulesIngestProtoPage`（交接說明要求）。參考畫面的測試改成測正式頁面，情境不變。
- 不改後端、不改 `state/`、不改 API。

## Capabilities

### New Capabilities
- `rules-ingest-page`：規則書匯入的正式頁面與權限。

### Modified Capabilities
- `frontend-shell`：新增「管理員才有的導覽項目」要求；既有的主要導覽列要求不變（非管理員看到的項目不變）。

## Impact

- 前端：`domains/rules_ingest/pages/`（新增）、`app/navigation.dart`、`app/router.dart`（永傑負責的共用區）。
- 刪除 `frontend/lib/prototypes/rules_ingest/`。
- 修改瑋鋐的測試 `manual_pages_widget_test.dart`、`manual_pages_route_test.dart`（參考畫面移除），MR 要 @ 瑋鋐。
- 和 `add-booking-notifications` 放在同一個分支與 MR（使用者決定）。
- `docs/handoff/rules_ingest.md` 仍寫「輸入桌遊編號」，與參考畫面現況（選桌遊名稱）不符，由瑋鋐更新。
