from typing import Protocol, runtime_checkable


@runtime_checkable
class Camera(Protocol):
    """攝影機介面。上層邏輯只依賴這個介面，不直接使用硬體套件。"""

    def capture(self) -> bytes:
        """取得一張影格（編碼後的影像資料）。"""
        ...
