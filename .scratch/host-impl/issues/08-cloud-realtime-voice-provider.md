# 08：阿里雲的 cloud 實作與外部服務測試

Status: resolved
Blocked by: 07
Spec: [spec](../../host/spec.md) §5.2、§7、§13.3
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

`backend/app/integrations/realtime_voice/cloud.py`：照 [01](01-merge-dev-and-realtime-voice-interface.md) 的介面接上阿里雲的 `Qwen-Audio-3.1-Realtime` Flash（新加坡區）。

1. 用 WebSocket 連阿里雲，把它的事件轉成介面定義的事件，把介面的動作轉成它的訊息。
2. 聲線代號對應：`male` 是 `xunanchuan_v3.1`、`female` 是 `longyuan_v3.1`（spec §7）。
3. 接話方式：`auto` 用 `smart_turn_v2`、靈敏度 0.5；`push_to_talk` 關掉自動接話。不用 `server_vad`。
4. 金鑰錯誤與連不上，都轉成介面的例外，由 `host` 回 `HOST_REALTIME_UNAVAILABLE`。
5. **要確認並回報的一件事**（spec §5.2）：阿里雲的事件帶不帶得出「這個工具請求屬於哪一句話」。帶得出來就照做；帶不出來，就改成「3 秒內同一個動作只執行一次」，回頭改 [07](07-websocket-and-relay.md) 的做法與測試，並更新 spec §5.2 那一條。
6. 動手前先讀原型怎麼連的：[`.scratch/host/prototypes/listen-test/`](../../host/prototypes/listen-test/)。事件名稱與欄位先查阿里雲的官方文件，不用記憶補；已查到的規格在 [Qwen 即時語音模型的官方規格](../../host/issues/01-qwen-realtime-facts.md)與[用真的聲音試聽 Qwen 主持人](../../host/issues/07-listen-to-qwen-host.md)。

金鑰用立倫本機 `.env` 的 `HOST_REALTIME_API_KEY`，會用到免費額度。立倫 2026-11-22 同意 AI 直接跑，不用每次問。測試只用文字輸入或組員自己的聲音，錄音檔不進 repo。

## 要動的檔案

- `backend/app/integrations/realtime_voice/cloud.py`（新）、`factory.py`
- `backend/tests/integrations/`（一般測試與 `external` 測試）
- `.scratch/host/spec.md`（只有第 5 點帶不出來時）

## 動到別人的地方

無。`integrations/realtime_voice/` 的擁有者是立倫。

## 驗收條件

- [x] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [x] 不需要金鑰的測試：事件轉換、聲線對應、接話方式的設定、錯誤轉換，用錄下來的事件樣本或手寫的假連線
- [x] 外部服務測試加 `@pytest.mark.external`，缺金鑰時直接失敗並說明缺哪個設定，不自動跳過（AGENTS.md §7.6）
- [x] 外部服務測試至少涵蓋：連得上並收到主持人的聲音；請主持人開口；工具請求與回工具結果；取消正在產生的回答
- [x] `uv run pytest -m external` 的結果（通過幾個、失敗幾個）記在本檔的 Comments，之後貼進 PR 說明
- [x] 第 5 點的結論記在本檔的 Comments
- [x] 整合層沒有 import `domains/` 的任何東西
- [x] AGENTS.md §2 第 7 點的後端三項檢查通過
- [x] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`

## Comments

- 2026-11-22：做完。事件名稱與欄位沒有用記憶補：照原型 2026-11-19 到 11-21 留在系統暫存區的實際事件紀錄（不含聲音）寫，再用外部服務測試對真的服務驗證。
- 2026-11-22 **第 5 點的結論：帶得出來，照 spec §5.2 原本的寫法做，spec 不用改。**
  - 工具請求的事件本身沒有「屬於哪一句話」的欄位，只有回答的編號。
  - 但順序是固定的：玩家的一句話收進對話（帶那句話的編號）→ 語音模型開始回答 → 這個回答裡的工具請求。所以 `cloud` 記下「每個回答是被哪一句話引出來的」，工具請求就對得出那句話的編號。
  - 辨識文字（片段與完整）帶的是同一個編號。外部服務測試 `test_spoken_question_calls_the_tool_and_tool_result_is_answered` 用真的服務確認過：工具請求與完整辨識文字的編號相同。
  - 對不出來的只有一種：後端自己請主持人開口的那個回答裡的工具請求（例如回完工具結果又接著呼叫工具）。這時編號是空的，轉送那一段改用「最近一句的辨識文字，同一個動作 3 秒內只執行一次」。
- 2026-11-22 外部服務測試的結果：
  - `uv run pytest -m external tests/integrations/test_realtime_voice_external.py`：**通過 6 個、失敗 0 個**（連跑兩次都一樣，每次約 36 秒）。涵蓋：連得上並收到主持人的聲音、請主持人開口、取消正在產生的回答、說話觸發工具請求與回工具結果、不出聲的系統訊息、按住說話放開後才回答、金鑰錯誤。
  - `uv run pytest -m external`（全部）：通過 14 個、錯誤 14 個。14 個錯誤都不是這張的：OCR 9 個、規則影片字型與輸出 3 個、TTS 1 個、檔案儲存 1 個，原因都是立倫這台機器的 `.env` 沒有那些服務的設定（測試照規定直接失敗並說明缺哪個欄位）。
- 2026-11-22 實作時量到、spec 沒寫的事：
  1. 對話裡還沒有玩家的訊息時，直接「請回答」會被拒。所以請主持人開口時，把要說的內容放成一則玩家角色的文字訊息（開頭註明是後端的指示），再請它回答。
  2. 被判定成不是在跟它說話的那句話，一樣有片段與完整的辨識文字（另一組事件），`cloud` 一併交出去。這樣主持人說話時玩家說「等一下」，後端看辨識文字的那條路才接得到。
  3. 主持人的一段話從「第一小段聲音」算開始，不是從回答建立算起；只呼叫工具、沒有聲音的回答不算一段話。
  4. 辨識文字是簡體字。轉繁體是 `host` 核對語音指令時做的，整合層不轉。
- 2026-11-22：測試不用任何人的聲音，也沒有存錄音。要「玩家說話」時，先請語音模型自己把那句話唸出來，聲音只留在記憶體，轉成 16 kHz 後餵給另一條連線。
- 2026-11-22：本機 `.env` 原本只有 `HOST_REALTIME_API_KEY` 與 `HOST_REALTIME_WORKSPACE_ID`。spec §13.4 的欄位是 `HOST_REALTIME_API_HOST`，所以在本機 `.env` 補了一行，由工作區編號組出新加坡區的整段 API Host（和原型的算法相同）。`.env` 不進 git。
