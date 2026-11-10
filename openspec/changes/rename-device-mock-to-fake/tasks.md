# Tasks

## 1. Spec 用詞（commit：docs: 統一測試替身用詞為 fake（AGENTS.md 7.5））

- [x] 1.1 確認改名前基準：在 `device/` 跑 `uv run pytest`，記下測試數量（實際 8）
- [x] 1.2 archive 時主 spec `openspec/specs/device-hardware-abstraction/spec.md` 須套用 delta；驗證：`openspec validate rename-device-mock-to-fake --strict` 通過

## 2. 程式改名（commit：refactor(device): mock 實作改名為 fake）

- [x] 2.1 `git mv` 兩個實作檔為 `fake_camera.py`、`fake_motor.py`，類別改 `FakeCamera`、`FakeMotor`，`TEST_FRAME` 的 `mock-frame` 改 `fake-frame`；驗證：`uv run ruff check .` 通過
- [x] 2.2 `git mv` 兩個測試檔為 `test_fake_camera.py`、`test_fake_motor.py`，函式 `test_mock_*`→`test_fake_*`，只改名稱不改斷言；驗證：`git diff` 檢視斷言行無變動
- [x] 2.3 更新 `tests/test_interface_only.py` 的 import 與使用處；驗證：該測試通過
- [x] 2.4 更新 `device/README.md` 說明（mock→fake、`hardware/fake_*.py`）；驗證：README 無 mock 字樣
- [x] 2.5 在 `device/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`；驗證：全部通過且測試數量與 1.1 相同
- [x] 2.6 全 repo 搜尋 mock（排除 `openspec/changes/archive/`、`.venv`、`build`、`.dart_tool`、`*.lock`）；驗證：無殘留（AGENTS.md 7.5 中的「mock 套件」說明除外）

## Workflow follow-up

- 兩個 commit 分開提交後執行 `/opsx:archive`，開 Draft MR 到 `dev`；MR 的測試案例表格寫「不適用：只改名稱，行為不變」。
