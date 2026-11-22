"""先音後畫的時間軸（spec rules-video-maker「先音後畫的時間軸」）。

旁白長度由呼叫端提供；這裡直接指定秒數，與 TTS 無關。
"""

from pathlib import Path

import pytest

from app.integrations.video import DEFAULT_STYLE, build_timeline, load_video
from app.integrations.video.model import Beat
from tests.integrations.video.support import base_data, segment, write_game


def _timeline(tmp_path: Path, data: dict, seconds: dict[str, float]):
    video = load_video(write_game(tmp_path, data))
    return build_timeline(video, lambda beat: seconds[beat.beat_key], DEFAULT_STYLE)


def _beat(timeline, key: str):
    return next(b for s in timeline.segments for b in s.beats if b.beat.beat_key == key)


def _no_cues(data: dict) -> dict:
    for seg in data["segments"]:
        for beat in seg["beats"]:
            beat["cues"] = []
    return data


def test_beat_length_from_narration(tmp_path: Path) -> None:
    timeline = _timeline(tmp_path, _no_cues(base_data()), {"b1": 3.0, "b2": 3.0, "b3": 3.0})
    assert _beat(timeline, "b1").duration == pytest.approx(3.55)
    assert _beat(timeline, "b1").audio_sec == pytest.approx(3.0)


def test_beat_min_length(tmp_path: Path) -> None:
    timeline = _timeline(tmp_path, _no_cues(base_data()), {"b1": 1.0, "b2": 3.0, "b3": 3.0})
    assert _beat(timeline, "b1").duration == pytest.approx(2.6)


def test_beat_extends_for_cues(tmp_path: Path) -> None:
    data = _no_cues(base_data())
    segment(data, "s1")["beats"][1]["cues"] = [
        {"at": 4.0, "do": "move", "target": "main.c1", "to": "sidebar@zone_a"}
    ]
    timeline = _timeline(tmp_path, data, {"b1": 3.0, "b2": 3.0, "b3": 3.0})
    # 移動 0.8 秒：4.0 + 0.8 + 0.3
    assert _beat(timeline, "b2").duration == pytest.approx(5.1)


def test_change_shifts_only_later_beats(tmp_path: Path) -> None:
    data = base_data()
    before = _timeline(tmp_path, data, {"b1": 3.0, "b2": 3.0, "b3": 3.0})
    after = _timeline(tmp_path, data, {"b1": 3.0, "b2": 4.0, "b3": 3.0})
    assert _beat(after, "b1").start == pytest.approx(_beat(before, "b1").start)
    assert _beat(after, "b2").start == pytest.approx(_beat(before, "b2").start)
    assert _beat(after, "b3").start == pytest.approx(_beat(before, "b3").start + 1.0)
    assert after.total == pytest.approx(before.total + 1.0)


def test_beat_type_is_data_only() -> None:
    # 段資料不存絕對秒數：Beat 沒有任何時間欄位
    assert not any("sec" in name for name in Beat.__dataclass_fields__)
