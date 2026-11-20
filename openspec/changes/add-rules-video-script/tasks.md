# Tasks

> 第 1 階段 1c（design.md D9，一個 MR）。先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節）；AI 只產出 MR 說明存到 `docs/mr_info/`，情境表格依類別分組並標示對應的測試（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置

- [x] 1.1 決定規則書來源、用語、產生範圍，驗證：記在 design.md Context
  - 結論（2026-11-21）：本機文字檔；用語對照表；產生到句內動作與區域名稱。
- [x] 1.2 永傑確認本 change 的情境表格，驗證：確認後才開分支
  - 2026-11-21：永傑要求直接開工，視為確認。
- [ ] 1.3 等 `add-rules-video-maker` 的 #75 合併，驗證：dev 上有 `integrations/video/pipeline.py`
  - 2026-11-21 決定：為了加快，本 MR 從 #75 的分支往下接，#75 合併後再把 dev 合併進來。
- [ ] 1.4 永傑把《血與刃》規則書第 5 頁的文字存成 `backend/.local/rules_video/rulebook/en-005.txt`，並寫好 `terms.json`（至少涵蓋手寫版用到的牌名、區域與陣營），驗證：檔案存在且不出現在 `git status`

## 2. MR（分支 `feature/rules_qa-video-script`，從 #75 的分支往下接）

- [x] 2.1 第一個 commit：本 change 的 OpenSpec 文件
- [x] 2.2 撰寫草稿模式的測試（`tests/integrations/video/test_draft.py`），驗證：測試存在且失敗
- [x] 2.3 撰寫逐項比對的測試（`tests/integrations/video/test_compare.py`），驗證：測試存在且失敗
- [x] 2.4 撰寫 AI 產生與檢查改寫的測試（`tests/rules_qa/test_video_script.py`，`FakeLLMProvider`），驗證：測試存在且失敗
- [x] 2.5 撰寫 `draft`、`compare` 指令的測試（`tests/rules_qa/test_video_commands.py`），驗證：測試存在且失敗
- [x] 2.6 ~~撰寫 external 測試~~：不做。AGENTS.md 7.6 只允許 `integrations/` 的測試需要金鑰；實際呼叫 LLM 改在 2.8 本機驗收（2026-11-21 修正）
- [x] 2.7 實作草稿模式、比對、AI 產生、檢查與改寫、兩個子指令，驗證：2.2–2.5 通過
- [ ] 2.8 用《血與刃》第 5 頁實際產生草稿，與手寫版逐項比對，加上 `--assets-from` 輸出靜態圖，驗證：**交給永傑看比對報告與靜態圖**
  - 第 1 版（2026-11-21）：5 段 9 句，一次通過檢查；round 被譯成「回合」（對照表沒有 round）。
  - 永傑決定（2026-11-21）：terms.json 補 round → 輪，並依 AGENTS.md §10.2 核對（另補 game → 局）；
    指示改為「規則寫泛稱時選一張具體代表牌，素材說明寫明店員可以替換」，不改對照表去湊手寫版；
    先不打勾，重新產生後再判斷。
  - 第 2 版：改寫一次後仍不通過，AI 把 cue 的 target 寫成 `highlight:<key>`。原因是指示沒有說明寫法，
    已補上並加測試。
  - 第 3 版：5 段 11 句，一次通過；round 已譯為「輪」。仍有：「局」沒被採用（game → 局 沒列 avoid）；
    代表牌仍是泛稱（第 5 頁與對照表沒有牌的分類，AI 無從選擇）；白薔薇被誤標為代表牌。
  - **已知問題：規則陳述不完整**。頁尾「直到一方獲勝或所有輪都結束」，AI 兩版都漏了「或所有輪都結束」。
    永傑要求在比對報告中標出這類情況（做法待確認，見對話）。
- [ ] 2.9 自我檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`、`uv run pytest -m external`，驗證：全部通過（external 的 OCR 項目除外）、CI 全綠，再改成 Ready for review

## Workflow follow-up

- 依比對結果，由永傑決定：要調整指示或用語對照表重新產生，還是可以進入 1d。
- MR 合併後，與 `add-rules-video-maker` 一起執行 `/opsx:archive`。
