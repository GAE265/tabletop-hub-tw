# 02：主持內容（常數、固定台詞草稿、規則要點、指令文字）

Status: resolved
Blocked by: 01
Spec: [spec](../../host/spec.md) §4
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

新檔案 `backend/app/domains/host/content.py`：主持人會說到的所有內容，以及交給語音模型的文字。全部是純函式與常數，不碰連線、不碰圖。

1. 門檻與圓版格數的常數（spec §4.4 的表，人數 5 到 10）。
2. 固定台詞 18 句（spec §4.1 的代號）。字句用草稿，出處在[白薔薇 demo 的主持規則：追加哪些、忽略哪些](../../host/issues/23-white-rose-demo-host-rules.md)的 Answer 第 4、8 節、[用 Flash 還是 Plus、要不要轉交思考模型](../../host/issues/09-model-lineup.md)的 Answer 第 3、4 節、[主持人能查哪些資料、誰能開主持](../../host/issues/13-host-tools-and-permissions.md)的 Answer 第 4 節。定稿在 [10](10-prototype-handoff-and-live-checks.md)。
3. 規則要點：三個階段各一組，完整版與簡短版（spec §4.2 的表；條目在「白薔薇 demo 的主持規則」Answer 第 3 節）。用哪一版只看第幾回合。交給主持人的格式照 spec §4.2 最後一點。
4. 組出完整指令（spec §4.3 的 12 項）與一句現況的文字。由程式組，不叫模型。
5. `back_to` 的文字：回合內說第幾回合的哪個階段；開場到夜晚說節點名稱。
6. 八個工具的定義（名稱與參數，spec §8.1），給開連線時傳給整合層。

規則書的內容只能用自己的話寫，不貼原文（AGENTS.md §2 第 2 點）。

## 要動的檔案

- `backend/app/domains/host/__init__.py`、`backend/app/domains/host/content.py`（新）
- `backend/tests/host/`（新）

## 動到別人的地方

無。

## 驗收條件

- [x] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [x] spec §4.5 的 C-01 到 C-05 每一行都有測試而且通過
- [x] 六種人數的門檻與格數都和 spec §4.4 的表相同
- [x] 18 個代號都拿得到文字；`answer_winning` 帶得出這局的兩個門檻
- [x] 八個工具的名稱與參數和 spec §8.1 相同
- [x] AGENTS.md §2 第 7 點的後端三項檢查通過
- [x] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`

## Comments

- 2026-11-22：做完。和本機規則書原文（`dev-postgres-1` 的 `games_manual` 與 `rules_qa_chunks`，只讀）比對過：規則要點、固定台詞、指令都沒有整句相同的句子。最長的相同片段是夜晚第一步點名四個角色那一句（14 個字，角色名稱加「請睜開眼睛」），是立倫在「白薔薇 demo 的主持規則：追加哪些、忽略哪些」看過的草稿，保留。
- 夜晚第二步的倒數寫成完整的十個數字（草稿原本是「十、九、八……一」），因為固定台詞要照唸。
