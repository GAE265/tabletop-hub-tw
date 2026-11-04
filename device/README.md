# device：發牌機（樹莓派 5）

發牌決策在樹莓派本機完成，網路斷線也要能出牌（見 [AGENTS.md](../AGENTS.md) 第 6 節）。

目前是骨架：只有攝影機與馬達的介面（`hardware/camera.py`、`hardware/motor.py`）和 mock 實作（`hardware/mock_*.py`），**沒有真實硬體驅動，也沒有 MQTT 連線**。上層邏輯只能依賴介面，不得 import 硬體專用套件。

## 開發機（Windows／Mac／Linux）

不需要樹莓派，也不需要安裝任何硬體套件。在 `device/` 執行：

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## 樹莓派上的環境

樹莓派 OS 上的 `picamera2` 要用 **apt** 安裝，不能用 pip／uv 安裝（相依的 `libcamera` 只有系統套件）：

```bash
sudo apt install -y python3-picamera2
```

因此虛擬環境必須能讀取系統套件（system site packages）：

```bash
uv venv --system-site-packages
uv sync
```

`picamera2` 不列入 `pyproject.toml` 的相依，這樣開發機與 CI 才能安裝並跑測試。真實硬體實作之後再補，並放在介面後面。
