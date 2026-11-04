from typing import Protocol, runtime_checkable


@runtime_checkable
class Motor(Protocol):
    """馬達介面。上層邏輯只依賴這個介面，不直接使用硬體套件。"""

    def rotate(self, degrees: float) -> None:
        """轉動指定角度，正負號代表方向。"""
        ...

    def stop(self) -> None:
        """立即停止。"""
        ...
