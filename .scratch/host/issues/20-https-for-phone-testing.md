# 手機實測怎麼拿到 HTTPS

Type: grilling
Status: closed
Blocked by: 12
Map: [AI 語音主持](../map.md)

## Question

手機瀏覽器要 HTTPS 才能用麥克風，連電腦的區網位址不算（「[Flutter Web 怎麼收音與即時播音](05-flutter-web-audio.md)」）。07 試聽只在 Mac 的 Chrome（localhost）做。「[聲音怎麼從瀏覽器連到模型](12-audio-connection-path.md)」定了手機要連後端的 WebSocket（`wss://`），頁面與後端都要 HTTPS。決定開發與驗收時怎麼讓桌上的手機或平板連得到：

1. 用哪種做法：臨時對外網址（例如通道服務）、本機自簽憑證並讓手機信任、或直接部署到 Azure 測。
2. 金鑰只在本機 `.env`，對外網址開著時誰連得到後端、要不要限制。
3. 誰的電腦與手機做實測（測試只用組員的聲音）。
4. 要不要寫進交接說明，讓組員也能照做。

## Comments

## Answer

2026-11-20 整理地圖時關閉，列為範圍外，**沒有單獨決定**。立倫要求依專案實務需要刪減 ticket。

原因：手機怎麼拿到 HTTPS 是開發與部署環境的事，不影響 spec 怎麼寫。本機開發用 Mac 的 Chrome 開 `localhost` 不需要 HTTPS，試聽就是這樣做的。

題目的去向：「[寫 spec.md](21-write-spec.md)」的驗收會寫一條前置條件：手機實測要有 HTTPS，由實測的人準備。做法（臨時對外網址、自簽憑證、或部署後再測）到要實測時再選。
