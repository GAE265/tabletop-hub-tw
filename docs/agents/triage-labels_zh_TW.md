# Triage labels

> 本檔是 [`triage-labels.md`](./triage-labels.md) 的繁體中文翻譯，給組員閱讀。mattpocock skills 的 agent 讀英文版；兩者內容不一致時，以英文版為準。

skill 一律用五個標準的 triage 角色來描述 issue 的狀態。本檔把這些角色對應到本 repo issue tracker 實際使用的標籤字串。

| mattpocock/skills 的標籤 | 本 repo tracker 的標籤 | 說明 |
|---|---|---|
| `needs-triage` | `needs-triage` | 需要維護者評估這個 issue |
| `needs-info` | `needs-info` | 等待回報者補充資訊 |
| `ready-for-agent` | `ready-for-agent` | 規格已完整，可以交給 AFK agent（不需要人在旁邊看著的 agent）處理 |
| `ready-for-human` | `ready-for-human` | 需要人工實作 |
| `wontfix` | `wontfix` | 不會處理 |

skill 提到某個角色時，使用上表對應的標籤字串。例如 skill 說「apply the AFK-ready triage label」（加上可交給 AFK agent 的 triage 標籤）時，就用 `ready-for-agent`。

要換成其他用語，請修改英文版 `triage-labels.md` 的「Label in our tracker」欄，讓它符合實際使用的用語（agent 只讀英文版），再同步更新本檔的表格。
