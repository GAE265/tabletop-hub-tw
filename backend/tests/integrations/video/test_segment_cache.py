"""段影片快取（spec rules-video-maker「完整影片輸出」的只重做有變的段，MR 3）。

用手寫的 FakeSegmentEncoder 記錄哪些段被編碼，不需要 ffmpeg。
"""

import json
from pathlib import Path

from app.integrations.video import (
    DEFAULT_STYLE,
    FontSet,
    Renderer,
    build_timeline,
    layout_video,
    load_video,
)
from app.integrations.video.encode import SegmentEncoder, encode_segments
from app.integrations.video.timeline import SegmentTiming
from tests.integrations.video.support import base_data, segment, write_game

FONTS = FontSet(None, None)


class FakeSegmentEncoder(SegmentEncoder):
    """手寫的 fake：不畫圖、不呼叫 ffmpeg，只記下被編碼的段並寫一個假檔案。"""

    def __init__(self) -> None:
        self.encoded: list[str] = []

    def encode(self, timing: SegmentTiming, renderer: Renderer, target: Path) -> None:
        self.encoded.append(timing.segment.segment_key)
        target.write_bytes(b"fake segment")


def _with_sidebar_text(data: dict) -> dict:
    segment(data, "s2")["slots"]["sidebar"] = {"kind": "bullets", "items": ["first rule"]}
    return data


def _encode(tmp_path: Path, data: dict, seconds: dict[str, float] | None = None) -> list[str]:
    folder = tmp_path / "game"
    if not (folder / "assets").exists():
        write_game(folder, data)
    else:
        (folder / "video.json").write_text(json.dumps(data), encoding="utf-8")
    video = load_video(folder)
    timeline = build_timeline(
        video, lambda beat: (seconds or {}).get(beat.beat_key, 3.0), DEFAULT_STYLE
    )
    layouts = layout_video(video, FONTS, DEFAULT_STYLE)
    renderer = Renderer(video, timeline, layouts, FONTS, DEFAULT_STYLE)
    encoder = FakeSegmentEncoder()
    clips = encode_segments(video, timeline, renderer, encoder, tmp_path / "cache", DEFAULT_STYLE)
    assert [c.segment_key for c in clips] == [s.segment_key for s in video.segments]
    assert all(c.path.is_file() for c in clips)
    return encoder.encoded


def test_unchanged_reuses_all_segments(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    assert _encode(tmp_path, data) == ["s1", "s2"]
    assert _encode(tmp_path, data) == []


def test_visual_change_reencodes_only_that_segment(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    _encode(tmp_path, data)
    segment(data, "s2")["slots"]["sidebar"]["items"] = ["changed rule"]
    assert _encode(tmp_path, data) == ["s2"]


def test_replaced_asset_file_reencodes_segments_using_it(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    _encode(tmp_path, data)
    # 換掉 blue.png 的內容（只有 s1 的牌用到 blue）
    from PIL import Image

    Image.new("RGB", (100, 160), (10, 200, 10)).save(tmp_path / "game" / "assets" / "blue.png")
    assert _encode(tmp_path, data) == ["s1"]


def test_narration_length_change_reencodes_timed_segments(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    _encode(tmp_path, data)
    # b1 變長：s1 的時間變了；進度條依全片長度，同一章的 s2 也要重做（第 1 階段的限制）
    assert _encode(tmp_path, data, {"b1": 4.0}) == ["s1", "s2"]


# --- #75 審核延後的項目（tasks 4.14）：清舊快取不能刪到別段 ---


def test_prefix_keys_do_not_delete_each_other(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    segment(data, "s2")["segment_key"] = "s1_2"  # 「s1」是「s1_2」的開頭
    assert _encode(tmp_path, data) == ["s1", "s1_2"]
    segment(data, "s1")["slots"]["main_title"]["text"] = "Case 1 changed"
    # 只重做 s1；s1_2 的快取還在（_encode 會確認每段的影片檔都存在）
    assert _encode(tmp_path, data) == ["s1"]


def test_keys_with_same_safe_name_keep_own_cache(tmp_path: Path) -> None:
    data = _with_sidebar_text(base_data())
    segment(data, "s1")["segment_key"] = "s/1"
    segment(data, "s2")["segment_key"] = "s-1"  # 轉成檔名後都是 s-1
    assert _encode(tmp_path, data) == ["s/1", "s-1"]
    assert _encode(tmp_path, data) == []
