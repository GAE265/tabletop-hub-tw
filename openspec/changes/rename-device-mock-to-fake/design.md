# Design

## Context

純用詞改名，動機見 proposal.md。目前 `device/` 有 `hardware/mock_camera.py`、`hardware/mock_motor.py`、`tests/test_mock_camera.py`、`tests/test_mock_motor.py`，另有 `tests/test_interface_only.py` 與 `README.md` 引用。

## Goals / Non-Goals

**Goals:**
- 名稱統一為 fake，測試數量與驗證內容和改名前完全相同。

**Non-Goals:**
- 不改行為、介面（`Camera`、`Motor`）、`MotorAction`。
- 不動封存檔與前端 `RecordingAdapter`。

## Decisions

- **用 `git mv` 改檔名**：保留 git 歷史；內容改名放同一個 commit。
- **Spec 以 ADDED（fake）+ REMOVED（mock）表達**：requirement 標題與 scenario 名稱都要改，MODIFIED 不允許更動 scenario 名稱（驗證器要求保留原有 scenario），所以用新增＋移除；內容與行為一致。
- **兩個 commit 分開**：docs（spec 用詞）與 refactor(device)（程式改名），符合 8.2 格式。
- **測試只改名稱**：函式名與 import 改名，斷言一概不動（7.5）。

## Risks / Trade-offs

- [漏改殘留 mock 字樣] → 改完在全 repo 搜尋 mock（排除 archive、.venv、build、.dart_tool、*.lock）確認。
- [測試數量變動] → 改名前後各跑一次 `uv run pytest`，數量須相同（目前 8 個）。
- [`.pytest_cache` 內有舊名稱] → 屬本機快取，不入版控，不處理。
