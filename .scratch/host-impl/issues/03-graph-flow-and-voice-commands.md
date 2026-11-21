# 03：圖之一（換節點、結束、語音指令核對、整局記憶）

Status: resolved
Blocked by: 02
Spec: [spec](../../host/spec.md) §3、§5、§9
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

新檔案 `backend/app/domains/host/graph.py`：LangGraph 的圖。每件事（按鍵、語音指令、裝置回報播完）跑一次圖（ADR 0004）。

1. 整局記憶的欄位（spec §9 的表），放 LangGraph 內建的記憶體儲存，一場主持一份。這張先做：人數、接話方式、聲線、節點、回合、階段、已結束、贏的一方。暫停、被打斷的那一段、最近 5 題留給 [04](04-graph-pause-resume-and-chatter.md) 與 [05](05-rules-lookup-and-thinking-model.md)，欄位可以先留好。
2. 換節點：下一步、上一步（spec §3.2 的表）、自動進（裝置回報播完才進，spec §3.1）、圓版放滿後的下一步當成結束。
3. 結束：三種觸發與三種結束台詞（spec §3.3）。結束後下一步、上一步不動。
4. 語音指令的核對（spec §5.2 的五個步驟）：問號不算、簡體轉繁體（小對照表，不加套件）、去標點與空白、去開頭的「主持人」、整句相符。說法清單照 spec §5.1。
5. 圖跑完交回「要做的事」的清單，例如：請主持人說哪一段內容、現況變了。這張與 04、05 的測試只看這份清單與記憶，不需要連線。真的去做這些事是 [07](07-websocket-and-relay.md) 的工作。

帶流程由程式決定，這張的圖裡沒有任何節點叫 LLM。

不在這張做：片段辨識文字等 0.3 秒、同一句話只執行一次、模型呼叫工具那一條路（都在 07）。

## 要動的檔案

- `backend/app/domains/host/graph.py`（新）
- `backend/tests/host/`

## 動到別人的地方

無。

## 驗收條件

- [x] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [x] spec §3.4 的 F-01 到 F-11、F-13 每一行都有測試而且通過（F-12 要有暫停，在 04）
- [x] spec §5.3 的 V-01 到 V-10 每一行都有測試而且通過
- [x] spec §4.5 的 C-06 到 C-08 每一行都有測試而且通過
- [x] spec §9 的 M-01、M-02、M-04、M-05 每一行都有測試而且通過（M-03 要有暫停，在 04）
- [x] 測試跑真的圖，不用 fake 取代圖（spec §13.1）
- [x] `graph.py` 沒有 import FastAPI 與任何模型廠商的 SDK（AGENTS.md §4.2）
- [x] AGENTS.md §2 第 7 點的後端三項檢查通過
- [x] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
