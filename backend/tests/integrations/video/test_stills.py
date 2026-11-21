"""靜態圖的檔名與輸出順序（spec rules-video-maker「本機指令與靜態圖」，#71 審核修正）。"""

from pathlib import Path

import pytest

from app.integrations.video import DEFAULT_STYLE, FontSet, Renderer, load_video, render_stills
from tests.integrations.video.support import base_data, segment, write_game

FONTS = FontSet(None, None)


def test_key_with_slash_gets_safe_file_name(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s2")["segment_key"] = "s2/final"
    segment(data, "s2/final")["beats"][0]["beat_key"] = "b3/end"
    video = load_video(write_game(tmp_path, data))
    result = render_stills(video, tmp_path / "out", FONTS, DEFAULT_STYLE)
    assert len(result.stills) == 7
    stills_dir = tmp_path / "out" / "stills"
    # 全部在同一個資料夾，沒有因為「/」產生子資料夾
    assert sorted(p.name for p in stills_dir.iterdir()) == sorted(p.name for p in result.stills)
    assert all(p.parent == stills_dir and "/" not in p.name for p in result.stills)


def test_failure_keeps_previous_stills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video = load_video(write_game(tmp_path, base_data()))
    first = render_stills(video, tmp_path / "out", FONTS, DEFAULT_STYLE)
    before = {p.name: p.read_bytes() for p in first.stills}

    real_render = Renderer.render
    calls = {"n": 0}

    def render_then_fail(self: Renderer, t: float):
        # 手寫的替身：畫兩張之後失敗，模擬輸出到一半出錯
        calls["n"] += 1
        if calls["n"] > 2:
            raise RuntimeError("中途失敗")
        return real_render(self, t)

    monkeypatch.setattr(Renderer, "render", render_then_fail)
    with pytest.raises(RuntimeError):
        render_stills(video, tmp_path / "out", FONTS, DEFAULT_STYLE)

    stills_dir = tmp_path / "out" / "stills"
    after = {p.name: p.read_bytes() for p in stills_dir.glob("*.png")}
    assert after == before
