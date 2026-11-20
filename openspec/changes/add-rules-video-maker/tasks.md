# Tasks

> 本 change 只做規格的第 1 階段 1a＋1b（design.md D13，三個 MR）。每個 MR 都先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節）；AI 只依 `.github/pull_request_template.md` 產出 MR 說明存到 `docs/mr_info/`，情境表格依類別分組並標示對應的測試（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置確認

- [x] 1.1 `integrations/tts`、`storage`、`video` 的擁有者寫進 AGENTS.md 第 3 節，驗證：AGENTS.md 1.11 已列出永傑
- [x] 1.2 決定 TTS、儲存與合成工具，驗證：結論記在本檔
  - 結論（2026-11-17）：TTS 用 Azure AI Speech（REST，用既有的 `httpx`）、儲存用 Azure Blob Storage（#42 已合併）、合成用 ffmpeg。
- [x] 1.3 規格決定 A1–A5、C1–C5，驗證：記在 design.md Context
- [x] 1.4 第 1 階段的驗證對象與素材，驗證：記在 design.md Context
  - 結論（2026-11-20）：《血與刃》步驟三（138.15–170.15 秒）；背景用暗色漸層；聲音 `zh-TW-YunJheNeural`；不需要玩家環形；動作只有 show、hide、flip、shuffle、move；手做版的飛入改成彈出；進度條只有一段，比對時排除；情況二的暗刃移進血刃區（見 1.9）。
- [x] 1.5 本機資料就位（`backend/.local/rules_video/reference/`、`assets/`），並以 `.git/info/exclude` 排除，驗證：`git status` 看不到這些檔案
- [x] 1.6 本機安裝 ffmpeg，驗證：`ffmpeg -version` 可執行（9.0.2）
- [x] 1.7 使用微軟正黑體，驗證：本機有 `C:\Windows\Fonts\msjh.ttc`（一般）與 `msjhbd.ttc`（粗體），可填進 `VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD`
  - 結論（2026-11-20）：用 Windows 內建的微軟正黑體，不安裝 Noto；Noto 留待之後替換（只改設定）。與手做版比對時，字型不同列為已知差異。
- [x] 1.8 永傑提供步驟三的規則書頁碼（`source_pages`），驗證：記在本機 `video.json`
  - 結論（2026-11-20）：英文版規則書 RC1 PDF 第 5 頁，`source_pages` 為 `[{"lang": "en", "page": 5}]`；於 2.10 寫進本機 `video.json`。
- [x] 1.9 永傑對照規則書，確認情況二的暗刃是否要移進盤面，驗證：結論記在本檔（不影響 MR 1）
  - 結論（2026-11-20）：先決定暗刃不移動（依規則書文字），後來永傑更正為暗刃也移進盤面右上的血刃區（`sidebar@blade_zone`），與手做版相同。

> 先前計畫的 API、資料表、前端精靈、發布移到 1c／1d，等第 1 階段結果確認後另開 change。

## 2. MR 1（1a）：段資料、版型、畫面狀態與靜態圖（分支 `feature/integrations-video-segments`）

- [x] 2.1 永傑開 Draft MR 1，貼上 `docs/mr_info/feature/integrations-video-segments.md` 的說明與分組情境表格，驗證：Draft MR 已存在
  - Draft MR：#71（2026-11-20）
- [x] 2.2 `.gitignore` 加上 `backend/.local/`，驗證：放進該資料夾的檔案不出現在 `git status`
- [x] 2.3 `GLOSSARY.md` 新增提案術語，驗證：段、句、句內動作（cue）、版型、槽位、素材、區域、必拍／選拍、玩家環形都有定義
- [x] 2.4 撰寫段資料驗證的單元測試（`backend/tests/integrations/video/test_video_data.py`，用假遊戲資料）：涵蓋 spec「段資料格式與驗證」每個 scenario，驗證：測試存在且失敗
- [x] 2.5 撰寫版型排版的單元測試（`test_layout.py`）：涵蓋「main_with_sidebar 版型」每個 scenario，驗證：測試存在且失敗
- [x] 2.6 撰寫時間軸的單元測試（`test_timeline.py`，旁白長度用 `FakeTTSProvider` 的估計方式）：一般、很短、動作比旁白長、改一句，驗證：測試存在且失敗
- [x] 2.7 撰寫畫面狀態的單元測試（`test_frame_state.py`）：涵蓋「句內動作與畫面狀態」每個 scenario，驗證：測試存在且失敗
- [x] 2.8 撰寫指令的測試（`backend/tests/rules_qa/test_video_commands.py`）：`check` 通過與失敗、`stills` 輸出張數與尺寸、沒有設定字型時的警告、字型檔不存在、驗證失敗時不輸出；`.ttc` 字型集合檔（index 0 可用、index 超出範圍）需要實際的微軟正黑體，寫在 `tests/integrations/video/test_fonts.py` 並加 `@pytest.mark.external` 在本機執行（MR 說明要附 `uv run pytest -m external` 結果），驗證：測試存在且失敗
- [x] 2.9 實作 `integrations/video/` 的段資料模型與驗證、`main_with_sidebar` 與 `title_card`、《血與刃》風格資料、排版、時間軸（旁白長度由呼叫端提供）、畫面狀態與五種動作、靜態圖；`rules_qa/video_commands.py` 的 `check`、`stills`；`core/config.py` 與 `.env.example` 加上 `VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD`、`VIDEO_FONT_INDEX`（@ 立倫）；新增 Pillow、numpy，驗證：2.4–2.8 全部通過
- [x] 2.10 手寫《血與刃》步驟三的 `video.json`（只放本機），在實際的盤面圖上精確量測區域座標，輸出靜態圖，與手做版同一時間點的畫面並排比對、調整風格數值，驗證：**交給永傑確認對照圖**（已知差異排除：進度條只有一段、字型不同、飛入改彈出、背景為漸層）
  - 進度（2026-11-20）：`video.json` 已寫好（3 段、4 句、7 個素材），盤面四個區域已在實際盤面圖上量測；輸出 25 張靜態圖、對照圖 `out/sheet.png`、與手做版並排的 `out/compare.png`（都在 `backend/.local/rules_video/`）。依並排比對調整了字幕、章節標籤、標題、紅色標籤的字級與位置，側欄圖片改成靠上對齊。
  - 永傑確認對照圖 OK（2026-11-20）。
- [x] 2.11 自我檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，驗證：全部通過、CI 全綠，再改成 Ready for review
  - 本機（2026-11-20）：ruff check、ruff format --check 通過；`uv run pytest` 1379 passed；`uv run pytest -m external` 11 passed、9 errors（都是 OCR，本機 `.env` 缺 `OCR_DI_ENDPOINT`，與本 MR 無關；本 MR 的 2 個字型測試通過）。#71 CI 全綠。

## 2b. #71 審核修正 MR（分支 `fix/integrations-video-review`，2026-11-21）

#71 審核意見中延後的項目，另開這個 MR 先做先合併（AGENTS.md 第 2 節規則 6：一個 MR 只做一件事）；MR 3 從合併後的 dev 開分支。每項都先補測試再修。

- [x] 2b.1 字幕兩行時，字幕框上緣（約 806 px）高於內容區下緣（840 px），會蓋住圖片底部約 34 px。驗證：兩行字幕時字幕框不與內容區重疊
  - 做法：字幕最多兩行，`subtitle_top` 依兩行的高度計算，內容區下緣改為 796；斷行後超過兩行時排版失敗並指出段與句
- [x] 2b.2 圖片有 `crop` 時，`regions` 套在裁切後的圖上，框與 `move` 的位置會錯。驗證：有 crop 時區域仍對準原圖上的同一處
  - 做法：區域一律以原圖為準記錄，排版時換算成裁切後的位置；用到不在 crop 範圍內的區域時，載入就失敗
- [x] 2b.3 `stills.py`：key 含「/」時輸出失敗而且舊圖已被刪 → 檔名把不允許的字元換成 `-`；先輸出到 `stills.tmp/`，全部成功才取代舊圖
- [x] 2b.4 `assets.py`：`crop` 太小時除以零 → 載入時 crop 寬、高至少 0.01；裁切時至少保留 1 像素
- [x] 2b.5 `model.py`：素材 `file` 可以用 `..` 或絕對路徑指到 `assets/` 以外 → 載入時檢查解析後的路徑在 `assets/` 內
- [x] 2b.6 `model.py`：`template` 不是字串時拋 `TypeError` → 改成驗證錯誤
- [ ] 2b.7 自我檢查與 Draft MR，驗證：全部通過、CI 全綠，再改成 Ready for review
  - 進度（2026-11-21）：Draft MR #74，CI 全綠，等審核。

## 3. MR 2：`integrations/tts`（可與 MR 1 平行）

- [x] 3.1 永傑開 Draft MR 2，AI 從 `specs/media-integrations` 的「文字轉語音」整理分組情境表格，驗證：Draft MR 已存在
- [x] 3.2 撰寫 fake、空白文字、缺少設定、無法使用、429 重試的單元測試（Azure 的 HTTP 回應用手寫的 fake transport，不用 mock 套件），驗證：測試存在且失敗
- [x] 3.3 撰寫 Azure 實際合成的 external 測試，缺少金鑰時直接失敗並說明缺哪個設定，驗證：`uv run pytest` 不執行它
- [x] 3.4 實作介面、fake、Azure 實作與 factory；`core/config.py` 與 `.env.example` 加上 `TTS_PROVIDER`、`TTS_REGION`、`TTS_API_KEY`、`TTS_VOICE`（@ 立倫），驗證：3.2 通過；本機 `uv run pytest -m external` 的結果寫進 MR 說明
- [x] 3.5 自我檢查（同 2.11），驗證：全部通過、CI 全綠，再改成 Ready for review
  - 結果（2026-11-20）：Draft MR #72（分支 `feature/integrations-tts`，從 dev 開，不改 openspec）；`uv run pytest` 1344 passed；`uv run pytest -m external` 10 passed、9 errors（OCR，本機缺 `OCR_DI_ENDPOINT`，與本 MR 無關；TTS 實際合成通過）；CI 全綠；httpx 移到正式依賴。

## 4. MR 3（1b）：TTS 時間軸、編碼、背景音樂、混音（MR 1、MR 2 合併後）

> 2026-11-21 決定：為了加快，MR 3 從 #74 的分支（`fix/integrations-video-review`）往下接，不等它合併；#74 合併後再把 dev 合併進 MR 3。
> - 段快取與進度條：第 1 階段接受限制。每段畫面都畫了進度條，旁白長度一變，同一章的段都會重新編碼；快取只在「只改畫面、不改長度」時有效，報告中註明。
> - TTS 未設定（`TTS_PROVIDER` 未填或為 fake）時，旁白為靜音、照常輸出並警告；警告與報告都註明「時間為估計值」。

- [ ] 4.1 永傑開 Draft MR 3，AI 從 `specs/rules-video-maker` 的「先音後畫的時間軸」（旁白快取）、「完整影片輸出」與 `specs/media-integrations` 的「ffmpeg 呼叫」整理分組情境表格，驗證：Draft MR 已存在
- [ ] 4.2 撰寫旁白快取的單元測試（文字沒變不重新呼叫 TTS），驗證：測試存在且失敗
- [ ] 4.3 撰寫 `content_hash` 與「只重做有變的段」的單元測試（用手寫的 `FakeSegmentEncoder` 記錄哪些段被編碼），驗證：測試存在且失敗
- [ ] 4.4 撰寫背景音樂的單元測試（長度、同長度可重現）、找不到 ffmpeg、編碼中斷不留壞檔的測試，驗證：測試存在且失敗
- [ ] 4.5 撰寫 external 測試：實際編碼、串接、混音，確認 1920×1080、30 fps、有音軌、長度與 `timing.csv` 一致，驗證：`uv run pytest` 不執行它
- [ ] 4.6 實作 TTS 接上時間軸、逐格渲染、ffmpeg 編碼與串接、背景音樂、混音、`timing.csv` 與報告；`video_commands render`；`core/config.py` 與 `.env.example` 加上 `FFMPEG_PATH`、`VIDEO_MUSIC_VOLUME`；新增 scipy，驗證：4.2–4.4 通過；本機 `uv run pytest -m external` 的結果寫進 MR 說明
- [ ] 4.7 用 2.10 的 `video.json` 以 Azure TTS 輸出《血與刃》步驟三完整影片，驗證：**交給永傑看完整支影片**，依「規則正確、新手能看懂」判斷，並與手做版比較
- [ ] 4.8 自我檢查（同 2.11），驗證：全部通過、CI 全綠，再改成 Ready for review

## Workflow follow-up

- **第 2 階段的前置項目**：進度條改成最後才疊上去（例如在 ffmpeg 合成時疊加），讓段影片不依賴全片長度，才能真正做到「只重做受影響的那一段」（2026-11-21 決定）。
- 第 1 階段結果確認後，由永傑決定 1c（AI 產生段資料與最小素材清單）與 1d（API、資料表、前端精靈、發布）怎麼做，另開 change。
- 三個 MR 都合併後，執行 `/opsx:archive`。
