# Proposal

## Why

AGENTS.md 7.5 規定測試替身一律稱為 fake（類別名稱以 `Fake` 開頭，不使用 mock 用語）。`device/` 的硬體替身仍叫 mock，spec 與程式用詞和團隊規則不一致。

## What Changes

- `device-hardware-abstraction` spec 的用詞由 mock 改為 fake（requirement 標題與兩個 scenario 名稱／內文），行為不變。
- `device/` 的程式、測試與 README 同步改名：`MockCamera`→`FakeCamera`、`MockMotor`→`FakeMotor`、檔名 `mock_*`→`fake_*`、`TEST_FRAME` 內容 `mock-frame`→`fake-frame`、測試檔與測試函式 `test_mock_*`→`test_fake_*`。
- 不修改 `openspec/changes/archive/` 內的封存檔；前端 `RecordingAdapter` 不動。
- 無 **BREAKING**：沒有對外契約（API、MQTT 主題、資料表）變動，無 migration。

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `device-hardware-abstraction`: 僅用詞修改（requirement「提供 mock 實作」改名為「提供 fake 實作」，scenario 名稱與內文 mock→fake），驗收行為不變。

## Impact

- Domain：`dealer`（`device/`），主責新善、協助立倫、永傑；`device/` 的共用區擁有者為新善。
- 契約：不改動（7.1 節所列各項皆無變動）；migration：無。
- 程式：`device/hardware/`、`device/tests/`、`device/README.md`。
- 文件：`openspec/specs/device-hardware-abstraction/spec.md`（於 archive 時由 delta 套用）。
