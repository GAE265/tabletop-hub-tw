# device-hardware-abstraction Specification

## Purpose

讓發牌機程式在沒有樹莓派與硬體的電腦上也能開發與測試，之後只需補真實實作。

## Requirements

### Requirement: 硬體包在介面後面
攝影機與馬達 SHALL 各自以介面定義；上層邏輯 MUST 只依賴介面，不得直接依賴具體硬體函式庫。

#### Scenario: 以介面使用
- **WHEN** 上層程式取得攝影機與馬達
- **THEN** 只透過介面方法操作，不 import 硬體專用套件

### Requirement: 無硬體環境可跑測試
`device/` 的測試 SHALL 在沒有樹莓派的電腦上通過。

#### Scenario: 在開發機執行
- **WHEN** 在一般 Windows／macOS／Linux 電腦執行 device 測試
- **THEN** 全部通過

### Requirement: README 說明樹莓派環境
`device/README.md` SHALL 說明：樹莓派上的 `picamera2` 以 apt 安裝，虛擬環境須能讀取系統套件（system site packages）。

#### Scenario: 說明存在
- **WHEN** 檢視 `device/README.md`
- **THEN** 載明 `picamera2` 以 apt 安裝及虛擬環境需能讀取系統套件，並說明本機開發機不需安裝

### Requirement: 骨架不接真實硬體與 broker
骨架階段 `device/` MUST NOT 含真實硬體驅動或 MQTT 連線實作。

#### Scenario: 檢視相依
- **WHEN** 檢視 `device/` 的相依套件
- **THEN** 不含攝影機或 GPIO 驅動套件

### Requirement: 提供 fake 實作
系統 SHALL 為攝影機與馬達各提供 fake 實作，行為可預測且不需任何硬體。

#### Scenario: fake 攝影機
- **WHEN** 對 fake 攝影機要求影格
- **THEN** 回傳預先設定的影格或固定測試影格

#### Scenario: fake 馬達記錄動作
- **WHEN** 對 fake 馬達下達轉動指令
- **THEN** 動作被記錄供測試檢查，且不拋出硬體錯誤
