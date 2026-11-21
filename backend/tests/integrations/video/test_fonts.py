"""字型集合檔（.ttc）的載入（spec rules-video-maker「本機指令與靜態圖」的 external 情境）。

需要 Windows 內建的微軟正黑體，CI 沒有，所以標記 external，
只在本機用 `uv run pytest -m external` 執行（AGENTS.md 7.6）。
找不到字型時直接失敗並說明，不自動跳過。
"""

from pathlib import Path

import pytest

from app.integrations.video import FontConfigError, FontSet

pytestmark = pytest.mark.external

REGULAR = Path(r"C:\Windows\Fonts\msjh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msjhbd.ttc")


@pytest.fixture
def ttc_files() -> tuple[str, str]:
    missing = [str(p) for p in (REGULAR, BOLD) if not p.is_file()]
    if missing:
        pytest.fail(
            f"找不到微軟正黑體字型檔：{'、'.join(missing)}（這個測試需要 Windows 內建字型）"
        )
    return str(REGULAR), str(BOLD)


def test_load_ttc_index0(ttc_files: tuple[str, str]) -> None:
    fonts = FontSet(*ttc_files, index=0)
    assert fonts.fallback is False
    assert fonts.warning is None
    # 中文字有實際寬度（不是缺字方塊的固定寬度）
    font = fonts.get(40)
    assert font.getbbox("規則")[2] > font.getbbox("規")[2] > 0
    assert fonts.get(40, bold=True).getbbox("規則")[2] > 0


def test_ttc_index_out_of_range(ttc_files: tuple[str, str]) -> None:
    with pytest.raises(FontConfigError) as exc:
        FontSet(*ttc_files, index=99)
    assert "VIDEO_FONT_INDEX" in str(exc.value)
