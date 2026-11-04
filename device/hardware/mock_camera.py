from collections.abc import Sequence
from itertools import cycle

# 固定測試影格：JPEG 檔頭加結尾標記，不是真實影像
TEST_FRAME = b"\xff\xd8mock-frame\xff\xd9"


class MockCamera:
    """不需硬體的攝影機。依序循環回傳預先設定的影格，未設定時回傳固定測試影格。"""

    def __init__(self, frames: Sequence[bytes] | None = None) -> None:
        self._frames = cycle(frames or [TEST_FRAME])

    def capture(self) -> bytes:
        return next(self._frames)
