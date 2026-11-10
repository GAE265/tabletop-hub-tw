# 02：建立 Foundry 並在 Azure 驗證

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §16、§17
MR: 不開 MR，結果跟著 08 的 MR 一起 commit

## 要做什麼

建立專題專用的 Foundry 與三個部署，照「[專題專用 Foundry 要部署哪些模型](../../games-advisor/issues/17-foundry-model-deployments.md)」。建好後手動驗證[整合層提案](../../games-advisor/integrations-proposal.md)第 10 節的 5 件事，不放進 pytest。建議最先做：驗證結果可能改到 04 的介面與 07 的 service。

## 驗收條件

- [ ] 建好三個部署：`gpt-5.6-luna`、`gpt-5.6-terra`、`text-embedding-3-large`（區域、部署類型、TPM 照 ticket 17 第 5 點）
- [ ] 確認 ticket 17 第 8 點的 3 件事：配額等級、額度是否和其他資源共用、有沒有限制區域的 policy；剩下的額度不到 NTD 1,000 時，`LLM_BATCH_MODEL` 留空
- [ ] 驗證提案第 10 節的 5 件事。AI 可以寫一次性的驗證腳本，腳本不進 repo
- [ ] 結果寫在本檔的 `## Answer`：第 4、5 點要記下 Azure 實際回的狀態碼與錯誤格式，08 用它們寫例外轉換
- [ ] 第 1 點不成立時改走提案的備案（「交卷」工具）：先改 spec 與提案，再做 07、08；04 已經合併的話，介面的修改放進 08
- [ ] 在 08 的分支把本檔的 `Status` 改成 `resolved`
