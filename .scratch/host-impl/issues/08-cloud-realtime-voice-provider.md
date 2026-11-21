# 08：阿里雲的 cloud 實作與外部服務測試

Status: ready-for-agent
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

- [ ] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [ ] 不需要金鑰的測試：事件轉換、聲線對應、接話方式的設定、錯誤轉換，用錄下來的事件樣本或手寫的假連線
- [ ] 外部服務測試加 `@pytest.mark.external`，缺金鑰時直接失敗並說明缺哪個設定，不自動跳過（AGENTS.md §7.6）
- [ ] 外部服務測試至少涵蓋：連得上並收到主持人的聲音；請主持人開口；工具請求與回工具結果；取消正在產生的回答
- [ ] `uv run pytest -m external` 的結果（通過幾個、失敗幾個）記在本檔的 Comments，之後貼進 PR 說明
- [ ] 第 5 點的結論記在本檔的 Comments
- [ ] 整合層沒有 import `domains/` 的任何東西
- [ ] AGENTS.md §2 第 7 點的後端三項檢查通過
- [ ] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
