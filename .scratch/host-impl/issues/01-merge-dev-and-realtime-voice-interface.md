# 01：接回 dev、套件與設定、即時語音的介面與 fake

Status: ready-for-agent
Blocked by: 無
Spec: [spec](../../host/spec.md) §13.2、§13.3、§13.4
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

替後面每一張打底，讓它們不用阿里雲金鑰就能寫測試。

1. 把 `dev` 接回 `feature/host`。已知只有 `GLOSSARY.md` 會衝突：`feature/host` 的「AI 語音主持（host）」與 `dev` 的「規則影片生產器」兩區都留。接回後先跑一次 AGENTS.md §2 第 7 點的檢查，確認是綠的再往下。
2. `backend/pyproject.toml`：加 `langgraph>=1.2.22,<2`；`websockets` 改成直接宣告。理由的草稿在[選哪個 Agent 框架、它負責什麼](../../host/issues/10-agent-framework-choice.md)的 Answer 第 7 節，寫 MR 說明時要用。
3. `core/config.py` 與 `.env.example`：spec §13.4 的五個欄位。`HOST_REALTIME_PROVIDER=cloud` 時缺欄位要啟動失敗。
4. `backend/app/integrations/realtime_voice/`：照 spec §13.3 做介面、型別、例外、`FakeRealtimeVoiceProvider` 與工廠。檔案的分法比照 `integrations/llm/`（`base.py`、`types.py`、`errors.py`、`fake.py`、`factory.py`）。`cloud` 實作留給 [08](08-cloud-realtime-voice-provider.md)，這張的工廠遇到 `cloud` 先丟「還沒實作」的錯誤。

fake 要做到：測試照劇本送出 spec §13.3「呼叫端會收到的事」的每一種事件；記下呼叫端做過的每一個動作；「請主持人開口」可以設定成被拒（兩種原因）。

## 要動的檔案

- `GLOSSARY.md`（只解衝突）
- `backend/pyproject.toml`、`backend/uv.lock`
- `backend/app/core/config.py`、`.env.example`
- `backend/app/integrations/realtime_voice/`（新）
- `backend/tests/integrations/`（新測試）、`backend/tests/core/`（設定的測試）

## 動到別人的地方

無。`integrations/realtime_voice/` 與 `core/` 的擁有者都是立倫（AGENTS.md §3）。

## 驗收條件

- [ ] `dev` 已接回，`GLOSSARY.md` 兩區都在
- [ ] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [ ] fake 的測試：每一種事件都送得出來；每一個動作都記得到；「請主持人開口」被拒時回報原因
- [ ] 設定的測試：預設是 `fake`；`cloud` 缺金鑰或 API Host 時啟動失敗
- [ ] 整合層沒有 import `domains/` 的任何東西（AGENTS.md §4.2）
- [ ] `.env.example` 只寫欄位名與說明（AGENTS.md §2 第 1 點）
- [ ] AGENTS.md §2 第 7 點的後端三項檢查通過
- [ ] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
