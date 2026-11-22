# 前端收音與播音用哪些套件

Type: grilling
Status: closed
Blocked by: 11, 12
Map: [AI 語音主持](../map.md)

## Question

「[聲音怎麼從瀏覽器連到模型](12-audio-connection-path.md)」定了手機只連我們的後端，走 WebSocket：聲音送原始 PCM（上行 16 kHz、下行 24 kHz 單聲道），其他訊息用 JSON。依「[Flutter Web 怎麼收音與即時播音](05-flutter-web-audio.md)」的研究，決定前端用什麼：

1. 收音：`record`、`flutter_sound`，或直接用瀏覽器的 API（包在 `core/platform/` 後面，AGENTS.md §5.3）。
2. 播音：邊收邊播、插話時立刻停播並清空待播內容、拒收舊回覆，用哪個套件或瀏覽器的 API 做得到。
3. 連線：`web_socket_channel`（目前只是間接相依，要改成直接宣告）。
4. `record` 7.x 與 `web` 1.1.2 會提高 Flutter SDK 的版本門檻：本機與組員的 Flutter 版本夠不夠、要不要升。動到前端共用區或 SDK 門檻要和永傑談（AGENTS.md §3）。
5. 新增套件的理由怎麼寫（AGENTS.md §2 第 4 點）。

## Comments

## Answer

2026-11-20 整理地圖時關閉，**沒有單獨決定**。立倫要求依專案實務需要刪減 ticket。

原因：選套件要實際裝起來試才知道，光討論定不了；而試聽原型已經有一個實測可用的做法。

題目的去向：改成預設做法，列在「[寫 spec.md](21-write-spec.md)」的第 7 到 9 點，寫 spec 時給立倫確認。

- 收音與播音直接用瀏覽器的 API，包在 `frontend/lib/core/platform/` 的介面後面，不新增音訊套件。試聽原型就是這樣做：`getUserMedia` 加 AudioWorklet 收 16 kHz，Web Audio 播 24 kHz，插話時停播並清空待播內容。
- 連線用 `web_socket_channel`，從間接相依改成直接宣告。
- 這樣不用提高 Flutter SDK 的版本：`record` 7.x 要 Flutter 3.44／Dart 3.12，專案目前宣告的最低版本是 Flutter 3.41／Dart 3.11.1。
- 實作時行不通，再回來選 `record` 6.x 或 `flutter_sound`。
