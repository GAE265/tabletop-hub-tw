# 測試案例優先的開發流程

> 本文件是 `AGENTS.md` 第 7 節的圖解版，給組員閱讀。規則以 `AGENTS.md` 為準。

![測試案例優先的開發流程](images/test-first-flow.png)

## 一句話說明

**測試案例是「事先約定要做對什麼」，發 MR 前的檢查是「確認現在的程式有沒有做到約定」。** 兩者是同一套測試，只是用在不同時間點。

## 流程圖（GitHub 上可直接顯示）

```mermaid
flowchart TD
    A["1. 開功能分支，開 Draft MR<br/>這時還沒有程式碼"]:::neutral
    B["2. 列測試案例表格<br/>組員確認「要做對什麼」"]:::human
    C["3. 寫測試程式並提交<br/>結果是紅燈，這是正常的"]:::red
    D["4. 寫功能<br/>目標：讓紅燈變綠燈"]:::green
    E{"5. 發 MR 前自我檢查<br/>全部綠燈了嗎？<br/>ruff、pytest、flutter"}:::green
    F["6. 改成 Ready for review<br/>CI 自動重新檢查"]:::human
    G["7. CI 通過 + 組員審核<br/>合併到 dev"]:::neutral

    A --> B --> C --> D --> E
    E -- "還有紅燈" --> D
    E -- "全部綠燈" --> F --> G

    subgraph draft ["Draft 期間：紅燈沒關係"]
        A
        B
        C
        D
        E
    end
    subgraph ready ["Ready 之後：必須全部綠燈"]
        F
        G
    end

    style draft fill:#FFFFFF,stroke:#993C1D,stroke-dasharray:5 5
    style ready fill:#FFFFFF,stroke:#0F6E56,stroke-dasharray:5 5
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A
    classDef human fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef red fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
    classDef green fill:#E1F5EE,stroke:#0F6E56,color:#04342C
```

顏色：紫色是要由人確認的步驟，紅色是紅燈階段，綠色是讓紅燈變綠燈的階段。

## 每一步在做什麼（以訂位功能為例）

| 步驟 | 做什麼 | 訂位功能的例子 |
|---|---|---|
| 1. 開 Draft MR | 開好功能分支就在 GitHub 開 Draft Pull request，還不需要有程式碼 | 分支 `feature/booking-create`，開 Draft |
| 2. 列測試案例 | 在 MR 說明寫「情境／操作／預期結果」表格，@ 一位組員確認 | 空桌可以訂、重複訂要擋、人數超過要擋、沒登入要擋 |
| 3. 寫測試並提交 | 把表格寫成測試程式。功能還沒做，所以測試全部失敗 | 4 個測試，全部紅燈 |
| 4. 寫功能 | 一個一個把紅燈變綠燈 | 寫訂位 API |
| 5. 自我檢查 | 跑下方所有指令。還有紅燈就回到第 4 步 | 4 個測試全部綠燈，檢查也通過 |
| 6. Ready for review | 把 Draft 改成 Ready for review，GitHub 會在乾淨的環境自動重跑檢查 | CI 執行中 |
| 7. 合併 | CI 通過，加上一位組員審核通過，合併到 `dev` | 合併完成 |

## 測試的三種分類

寫測試前，先判斷它屬於哪一類（`AGENTS.md` 7.6）：

| 分類 | 測什麼 | 例子 | 需要金鑰 | CI 會跑嗎 |
|---|---|---|---|---|
| **單元測試** | 單一層的邏輯，依賴用假的實作取代 | 訂位 service 判斷「人數超過要擋」 | 不需要 | 會 |
| **API 測試** | 打 API 端點，驗證狀態碼、回應格式、權限 | `POST /api/v1/bookings` 沒登入回 401 | 不需要 | 會 |
| **外部服務測試** | `integrations/` 實際連到 Azure 等外部服務 | Azure OpenAI 真的回得出文字 | 需要 | **不會** |

重點只有一句：**只有 `integrations/` 的測試可以需要金鑰。** 其他功能（例如選遊顧問、規則問答）的測試一律用假實作（例如 `FakeLLMProvider`），所以不用金鑰也能跑，CI 也能檢查。

## 發 MR 前自我檢查的指令

**後端**（在 `backend/` 資料夾執行）：

| 指令 | 檢查什麼 |
|---|---|
| `uv run ruff check .` | 程式碼有沒有常見錯誤、import 排序 |
| `uv run ruff format --check .` | 程式碼格式是否統一（要自動修正就拿掉 `--check`） |
| `uv run pytest` | 所有測試是否通過（預設不跑外部服務測試） |
| `uv run pytest -m external` | **只有改到 `integrations/` 才需要跑。** 執行前先在 `.env` 填好金鑰，結果貼到 MR 說明 |

**前端**（在 `frontend/` 資料夾執行）：

| 指令 | 檢查什麼 |
|---|---|
| `flutter analyze` | 程式碼有沒有錯誤或不建議的寫法 |
| `flutter test` | 所有測試是否通過 |

只改後端就只跑後端，只改前端就只跑前端；兩邊都改就全部跑。

## 常見問題

**Q：為什麼 Draft 期間可以紅燈？**
紅燈是這個流程的起點，代表「還沒做完」，不是「做錯了」。Draft 不會被合併，所以不會影響任何人。

**Q：為什麼不能先寫功能再補測試？**
先寫功能再補測試，AI 很容易照著已經寫好的程式去寫測試，結果測試只是在描述程式「現在的樣子」，而不是「應該做到的事」。先把約定寫下來給人確認，測試才真的抓得到錯誤。

**Q：測試好像寫錯了，可以改嗎？**
可以，但不能為了讓測試通過而偷改。在 MR 說明寫出為什麼測試是錯的，審核者同意後才能改。

**Q：可以用 `xfail` 或 `skip` 先讓紅燈消失嗎？**
不行。這等於把警報關掉，問題還在。

唯一的例外是外部服務測試：加上 `@pytest.mark.external` 標記後，由設定檔統一不在預設執行與 CI 裡跑。這是事先講好的**分類**，不是臨時把失敗藏起來。

**Q：需要金鑰的測試，在 CI 不跑，那誰來確認它沒壞？**
改到 `integrations/` 的人。在本機填好 `.env` 後執行 `uv run pytest -m external`，把結果貼在 MR 說明，審核者會看。

**Q：沒有金鑰時，external 測試可以自己跳過嗎？**
不行。沒有金鑰就要**直接失敗，並寫清楚缺哪個設定**。如果寫成「沒有金鑰就跳過」，你以為測過了，其實什麼都沒測。

**Q：我的功能用到 LLM，測試一定要金鑰嗎？**
不用。功能的測試用 `integrations/` 提供的假實作，只測「拿到 LLM 回答之後，你的程式有沒有處理對」。LLM 本身能不能連上，是外部服務測試的事。如果你發現功能的測試非要金鑰不可，代表程式直接呼叫了外部服務，沒有經過 `integrations/`，要先改分層。