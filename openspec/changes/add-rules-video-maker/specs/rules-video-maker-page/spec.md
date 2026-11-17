# Spec Delta

## Purpose

前端規則影片製作精靈，只給店家人員與管理員使用。依專案狀態顯示目前這一步：拍說明書（需要時）→ 確認腳本 → 拍攝素材 → 合成 → 預覽與發布。`prototypes/rules_video/` 參考畫面與正式頁面共用同一份 `state/`。

## ADDED Requirements

### Requirement: 入口與權限
規則影片製作的入口 SHALL 只對 `shop_staff` 與 `admin` 顯示；`player` 看不到入口，直接開啟路由時顯示「只有店家人員可以使用影片製作」。

#### Scenario: 店家人員看到入口
- **WHEN** 目前使用者是 `shop_staff`
- **THEN** 顯示「規則影片製作」入口

#### Scenario: 玩家看不到
- **WHEN** 目前使用者是 `player`
- **THEN** 不顯示入口；直接開啟路由時顯示沒有權限的說明

### Requirement: 選遊戲與說明書
選擇遊戲後，若後端回 `RULES_VIDEO_NO_RULEBOOK`，畫面 SHALL 引導店員逐頁拍攝說明書並匯入（使用 `rules_ingest` 的匯入 API），匯入完成後再建立專案；這款遊戲已有規則書時直接建立專案。

#### Scenario: 已有規則書
- **WHEN** 選擇已入庫規則書的遊戲
- **THEN** 顯示「產生腳本中…」，完成後進入確認腳本

#### Scenario: 還沒有規則書
- **WHEN** 建立專案回 409 `RULES_VIDEO_NO_RULEBOOK`
- **THEN** 顯示「這款遊戲還沒有規則書，請先逐頁拍攝說明書」與拍照上傳區；全部頁面匯入後，按「產生腳本」重新建立專案

### Requirement: 確認腳本
`script_draft` 時 SHALL 逐段顯示標題與旁白的文字欄位，可以修改後「儲存」，最後「確認腳本」。確認前跳出提醒「確認後就不能再修改腳本」。

#### Scenario: 修改並確認
- **WHEN** 修改第 2 段旁白，按「儲存」再按「確認腳本」並確定
- **THEN** 依序呼叫修改腳本與確認腳本的 API，畫面進入拍攝素材

#### Scenario: 旁白空白
- **WHEN** 某段旁白是空白就按「儲存」
- **THEN** 該欄位顯示「請填寫旁白」，不呼叫 API

### Requirement: 拍攝素材
`collecting_materials` 時 SHALL 依段落分組列出素材，每項顯示說明、是否已上傳與縮圖，可以拍照或選檔上傳、重拍。全部上傳後「開始合成」才可以按。

#### Scenario: 上傳素材
- **WHEN** 對第 1 項素材選一張照片
- **THEN** 上傳完成後顯示縮圖與「已上傳」，進度更新為「1／N 項」

#### Scenario: 還有素材沒拍
- **WHEN** 還有素材未上傳
- **THEN** 「開始合成」停用，並顯示還差幾項

#### Scenario: 上傳失敗
- **WHEN** 上傳回 400 或 503
- **THEN** 該項顯示後端的錯誤訊息，可以重試

### Requirement: 合成與發布
`rendering` 時 SHALL 顯示「影片合成中」並每 5 秒重新查詢狀態；`ready` 時顯示影片預覽與「發布為教學影片」；`failed` 時顯示錯誤訊息與「重新合成」。發布前若這款遊戲已有教學影片，提醒「發布後會取代目前的教學影片」。

#### Scenario: 合成完成
- **WHEN** 查詢到 `status=ready`
- **THEN** 停止重新查詢，顯示影片預覽與「發布為教學影片」

#### Scenario: 合成失敗
- **WHEN** 查詢到 `status=failed`
- **THEN** 停止重新查詢，顯示 `error_message` 與「重新合成」

#### Scenario: 發布
- **WHEN** 按「發布為教學影片」並確定
- **THEN** 呼叫發布 API，顯示「已發布，玩家可以在規則教學看到這支影片」

#### Scenario: 離開頁面
- **WHEN** 合成中離開頁面
- **THEN** 停止重新查詢；回到專案時依目前狀態顯示對應步驟
