# 02：建立 Foundry 並在 Azure 驗證

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §16、§17
MR: 不開 MR，結果跟著 08 的 MR 一起 commit

## 要做什麼

建立專題專用的 Foundry 與三個部署，照「[專題專用 Foundry 要部署哪些模型](../../games-advisor/issues/17-foundry-model-deployments.md)」。建好後手動驗證[整合層提案](../../games-advisor/integrations-proposal.md)第 10 節的 5 件事，不放進 pytest。建議最先做：驗證結果可能改到 04 的介面與 07 的 service。

## 驗收條件

- [x] 建好三個部署：`gpt-5.6-luna`、`gpt-5.6-terra`、`text-embedding-3-large`（區域、部署類型、TPM 照 ticket 17 第 5 點）
- [x] 確認 ticket 17 第 8 點的 3 件事：配額等級、額度是否和其他資源共用、有沒有限制區域的 policy；剩下的額度不到 NTD 1,000 時，`LLM_BATCH_MODEL` 留空
- [x] 驗證提案第 10 節的 5 件事。AI 可以寫一次性的驗證腳本，腳本不進 repo
- [x] 結果寫在本檔的 `## Answer`：第 4、5 點要記下 Azure 實際回的狀態碼與錯誤格式，08 用它們寫例外轉換
- [x] 第 1 點不成立時改走提案的備案（「交卷」工具）：先改 spec 與提案，再做 07、08；04 已經合併的話，介面的修改放進 08（第 1 點成立，不適用）
- [ ] 在 08 的分支把本檔的 `Status` 改成 `resolved`

## Answer

2026-11-09 建立 Foundry 並驗證完成。資源名稱、端點、金鑰只寫在立倫的 `.env`，不寫進 repo（AGENTS.md §2.1）。

**結論**：第 1–3 點都成立，不用改走「交卷」備案，04 的介面不用改。第 4 點要多轉換一種錯誤（見下方「給 08 的轉換規則」）。

### 1. 建好的資源

| 部署名稱 | 模型（版本） | 部署類型 | TPM | 內容過濾 |
|---|---|---|---|---|
| `gpt-5.6-luna` | gpt-5.6-luna（2026-07-09） | GlobalStandard | 100K | `Microsoft.DefaultV2` |
| `gpt-5.6-terra` | gpt-5.6-terra（2026-07-09） | GlobalStandard | 50K | `Microsoft.DefaultV2` |
| `text-embedding-3-large` | text-embedding-3-large（1） | GlobalStandard | 100K | `Microsoft.DefaultV2` |

- Foundry：AIServices S0，Japan East，建在立倫的學員資源群組。
- 端點格式：`https://<資源名稱>.openai.azure.com/openai/v1/`。
- 冒煙測試：embedding 帶 `dimensions=1536` 回 1536 維；terra 能正常回答。

### 2. ticket 17 第 8 點的 3 件事

| 項目 | 結果 |
|---|---|
| 配額 | Japan East 的 GlobalStandard 可用量：luna 1,000K、terra 90K、embedding 1,250K TPM，三個都夠。terra 只剩 90K，因為額度池和其他學員共用 |
| 配額等級 | 沒有 API 能直接查。luna 可用 1,000K，比 Tier 1 的預設 250K 高，確定不是 Tier 0 |
| 額度是否共用 | 共用。資源群組的預算涵蓋群組內所有資源，查詢當下已用約 NTD 764；以額度 NTD 3,000 計，還剩約 NTD 2,236 |
| 區域限制 policy | 沒有。資源群組本身與繼承來的 policy 都是空的 |

剩下的額度超過 NTD 1,000，所以 `LLM_BATCH_MODEL` 維持 `gpt-5.6-terra`。

### 3. 提案第 10 節的 5 件事

用 `openai` 3.46.0 的 `OpenAI(base_url=v1 端點)` 呼叫，`gpt-5.6-luna`、`reasoning.effort: low`、`store: true`、`parallel_tool_calls: false`。

**第 1 點：成立。**
- 同一個請求帶 `search_games`（strict）與 `text.format`（strict json_schema）：第 1 次回 `function_call`，參數符合 schema。
- 送回 `function_call_output` 並接上 `previous_response_id`：第 2 次回 `message`，內容通過 `jsonschema` 驗證，推薦理由只用了工具資料。

**第 2 點：成立。**
- 送回工具結果時帶 `tool_choice: "none"`：回 `message`，符合 schema。
- 已有工具呼叫紀錄的對話，再送一則明顯需要查詢的新訊息（「換成 6 個人、陣營推理」），帶 `tool_choice: "none"`：模型沒有呼叫工具，回符合 schema 的訊息，`recommendations` 是空陣列，`reply` 說明目前無法查詢。

**第 3 點：成立。** 所有請求都送到 `POST .../openai/v1/responses`，網址沒有 `api-version`。

**第 4 點：`previous_response_id` 無效。** 都是 HTTP 400、`openai.BadRequestError`，但 `code` 分兩種：

| 情況 | `error.code` | `error.param` | `error.message` |
|---|---|---|---|
| 格式正確但不存在（`resp_000…`） | `previous_response_not_found` | `previous_response_id` | `Previous response with id '<id>' not found.` |
| 已刪除（模擬過期） | `previous_response_not_found` | `previous_response_id` | 同上 |
| 用 `store: false` 產生的 id | `previous_response_not_found` | `previous_response_id` | 同上 |
| 亂填、不是 `resp` 開頭（`not-a-valid-id`） | `invalid_value` | `previous_response_id` | `Invalid 'previous_response_id': '<id>'. Expected an ID that begins with 'resp'.` |

錯誤格式：

```json
{"error": {"message": "...", "type": "invalid_request_error",
           "param": "previous_response_id", "code": "previous_response_not_found"}}
```

- 別的 Foundry 資源產生的 id 沒有實測（目前只有一個專題用的資源）。Azure 把 response 存在各自的資源裡，預期和「已刪除」一樣回 `previous_response_not_found`。

**第 5 點：內容過濾。** 擋下輸入和擋下輸出的形式完全不同。

擋下輸入（用 jailbreak 訊息觸發預設 `Microsoft.DefaultV2` 的 prompt shield）：HTTP 400、`openai.BadRequestError`。帶不帶 `tools`、`text.format` 結果都一樣。

```json
{"error": {
  "message": "The response was filtered due to the prompt triggering Azure OpenAI’s content management policy. ...",
  "type": "invalid_request_error", "param": "prompt", "code": "content_filter",
  "content_filters": [{"blocked": true, "source_type": "prompt",
    "content_filter_results": {"hate": {"filtered": false, "severity": "safe"}, "...": "...",
                               "jailbreak": {"detected": true, "filtered": true}}}],
  "innererror": {"code": "ContentFiltered"}}}
```

擋下輸出（在臨時部署掛上自訂過濾、把輸出的暴力門檻調成 Low 來觸發；測完已刪除臨時部署與自訂過濾）：**HTTP 200，不會拋例外**。

| 欄位 | 值 |
|---|---|
| `status` | `"incomplete"` |
| `incomplete_details` | `{"reason": "content_filter"}` |
| `output` | `message` 項目的 `status` 也是 `"incomplete"`；推理模型前面可能多一個 `reasoning` 項目 |
| `output_text` | 被換成 `"I'm sorry, but I cannot assist with that request."` |
| `usage.output_tokens` | 照樣計費（模型實際產生的 token） |

- 帶 `text.format`（json_schema）時，`output_text` 一樣被換成上面那句英文，**不是 JSON**。

### 4. 給 08 的轉換規則

| Azure 的回應 | 轉成 |
|---|---|
| 400，`code == "previous_response_not_found"` | `LLMConversationNotFound` |
| 400，`code == "invalid_value"` 且 `param == "previous_response_id"` | `LLMConversationNotFound`（照提案「亂填也一律轉換」） |
| 400，`code == "content_filter"` | `LLMOutputRejected` |
| 200，`status == "incomplete"` 且 `incomplete_details.reason == "content_filter"` | `LLMOutputRejected` |

- 輸出被擋時是 200，所以一定要**先檢查 `status`，再解析 `output_text`**；否則會變成「不是合法 JSON」，雖然同樣是 `LLMOutputRejected`，但 log 會看不出原因。
- `status == "incomplete"` 而 `reason == "max_output_tokens"`（被截斷）照提案也轉 `LLMOutputRejected`，可以和內容過濾共用同一個判斷。
- 模型拒答（`refusal` 內容）沒有實測。

### 5. 其他觀察

- 簡單的請求在 `low` 下 `reasoning_tokens` 是 0，第 1 點的兩次呼叫合計輸入 752、輸出 178 token。
- 這次驗證全部的呼叫費用不到 NTD 1。
