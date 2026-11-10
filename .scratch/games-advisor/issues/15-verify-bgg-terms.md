# 核對 BGG 使用條款原文

Type: task
Status: resolved
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「桌遊基本資料從哪裡取得」的研究只能從搜尋引擎索引間接讀到 BGG 條款，因為 BGG 對自動存取一律回 Cloudflare 403。請用瀏覽器開啟下面三頁原文核對：

1. https://boardgamegeek.com/using_the_xml_api
2. https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use
3. https://boardgamegeek.com/terms 的第 6.B.iv 條

確認並記錄：

1. 是否禁止把 BGG 資料用在 AI／LLM 系統，包含即時查詢。
2. 能不能把資料存進自己的資料庫。
3. 本平台有桌遊店訂位功能，會不會被視為商業用途（參考 https://boardgamegeek.com/wiki/page/BGG_XML_API_Commercial_Use）。
4. 要不要向 BGG 申請非商業用途的書面同意。

這張的結論也會影響「英文與繁中心得從哪裡取得」：BGG 的評論與評分留言受同一份條款規範。

## Answer

2026-11-06 立倫用瀏覽器核對網站條款 6.B.iv 原文。

1. **AI／LLM：允許一般用途。** 條款標題是「General-purpose AI use is permitted」：可以把網站內容交給 AI 系統（含 LLM）做摘要、翻譯、搜尋、回答問題等一般用途；只禁止大型 AI 公司拿來訓練或微調模型。
   - 兩份研究讀到的是 2026-10-18 存檔的舊版（「不得當作 AI／LLM 系統的資料」），條款之後已經改了。
   - games_advisor 的用途是推論，不是訓練：把桌遊資料交給 LLM 比對與回答，用心得產生標籤（屬於摘要）。Azure OpenAI 也不會拿提示訓練模型。
   - XML API 條款（存檔版）禁止的是「訓練」AI／LLM，不影響我們的用途。現行版本沒有核對。
2. **能不能存進資料庫：還沒核對原文。** 移到「收錄哪些桌遊、存哪些欄位」決定匯入方式時一併確認。
3. **商業用途：** 依立倫說明，本專案是學習成果展示，沒有轉商用的計畫，視為非商業用途。預計只收錄約 3–15 款遊戲，不大量抓取。
4. **書面同意：** 不必為了 AI 用途另外申請。使用 XML API 仍要註冊 application 取得 token，並依條款標示來源。

## Comments

- 2026-11-06 立倫：BGG 不同意把資料用在商業用途；本專案只是學習成果展示，沒有轉商用的計畫。不會大量抓取，預計只收集約 3–15 款遊戲。
  - 第 3 題（商業用途）：依立倫說明，視為非商業用途。
  - 仍待核對：第 1 題（AI／LLM 條款原文）、第 2 題（能不能存進資料庫）、第 4 題（要不要申請書面同意）。AI 條款和商業用途是兩件事，非商業用途也可能受限。
