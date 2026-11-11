# 08：雲端實作

Status: ready-for-agent
Blocked by: 02、04（原本的 11 已由 #18 寫進 AGENTS.md 7.6）
Spec: [spec](../../games-advisor/spec.md) §16、§17
MR: （還沒開）

## 要做什麼

做 LLM 與 embedding 的雲端實作（Azure OpenAI），測試用 httpx `MockTransport` 假造 Azure 的回應，不連網路。例外怎麼轉換，照 02 記下的 Azure 實際回應。同時更新 OpenSpec 的 `llm-provider` 規格。

另外加上提案 §11.6 的 4 個外部服務測試（AGENTS.md 7.6），在本機確認真的連得上 Azure。`external` 標記 #18 已經註冊在 `backend/pyproject.toml`，不用再改。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] [整合層提案](../../games-advisor/integrations-proposal.md) §11.4、§11.5 的每一列都有測試而且通過
- [ ] 提案 §11.1 中需要雲端實作的 4 列也通過：`cloud` 設定齊全、`cloud` 缺欄位、`local` 的既有測試改參數、embedding 的 `cloud` 缺欄位
- [ ] 提案 §11.6 的 4 個外部服務測試加上 `@pytest.mark.external`，在本機通過；MR 說明貼上 `uv run pytest -m external` 的結果（通過幾個、失敗幾個），情境表格中這 4 列標「（本機）」（AGENTS.md 7.6）
- [ ] 缺少金鑰或設定時，外部服務測試直接失敗並說明缺哪個欄位；這個 fixture 放在 `backend/tests/integrations/conftest.py`，不放進 `integrations/llm`（#18），確認 `uv run pytest` 不會跑到這些測試
- [ ] 兩個既有測試照提案第 9 節第 2 點修改，MR 說明寫出理由，經審核者同意（AGENTS.md §7.5）
- [ ] MR 說明寫新增 `openai` 套件的理由（提案第 8 節、AGENTS.md §2.4）
- [ ] 開一個 OpenSpec change 更新 `llm-provider` 規格（提案第 9 節第 6 點）；同一個 change 也更新 `ci-checks`，寫明 `external` 測試不在 CI 跑（AGENTS.md 7.6）
- [ ] `.env.example` 兩處「cloud（尚未實作）」的說明改成已實作
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] MR @ 瑋鋐（整合層擁有者）
- [ ] 合併前把本檔與 02 的 `Status` 改成 `resolved`、`MR` 填上連結
