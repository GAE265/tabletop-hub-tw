"""進度條最後才疊上去（spec rules-video-revision「進度條最後才疊上去」，第 2 階段 MR 1）。

不需要 ffmpeg：段影片與靜態圖直接檢查 Renderer 畫出的圖；整支影片用手寫的假 ffmpeg 指令稿。
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.integrations.video import (
    DEFAULT_STYLE,
    FontSet,
    Renderer,
    VideoRenderError,
    build_timeline,
    layout_video,
    load_video,
)
from app.integrations.video.encode import FfmpegSegmentEncoder, frame_times
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.render import progress_box, progress_strip
from app.integrations.video.timeline import Timeline
from tests.integrations.video.support import (
    base_data,
    fake_ffmpeg,
    fake_ffmpeg_calls,
    write_game,
)

FONTS = FontSet(None, None)
GOLD = np.array(DEFAULT_STYLE.gold)


def _renderer(tmp_path: Path) -> Renderer:
    video = load_video(write_game(tmp_path / "game", base_data()))
    timeline = build_timeline(video, lambda beat: 3.0, DEFAULT_STYLE)
    layouts = layout_video(video, FONTS, DEFAULT_STYLE)
    return Renderer(video, timeline, layouts, FONTS, DEFAULT_STYLE)


def _box(image: Image.Image) -> np.ndarray:
    x, y, w, h = progress_box(DEFAULT_STYLE)
    return np.asarray(image.convert("RGB"))[y : y + h, x : x + w].astype(int)


def _gold_ratio(pixels: np.ndarray) -> float:
    """進度條那一條中，金色像素所在的欄數比例。"""
    gold = (np.abs(pixels[..., :3] - GOLD) <= 6).all(axis=-1)
    return float(gold.any(axis=0).mean())


def _mid(timeline: Timeline) -> float:
    # 段的中間：避開段開頭的淡入
    seg = timeline.segments[-1]
    return (seg.start + seg.end) / 2


def test_segment_frames_have_no_progress_bar(tmp_path: Path) -> None:
    renderer = _renderer(tmp_path)
    t = _mid(renderer.timeline)
    frame = renderer.render(t, progress=False)
    # 進度條的位置只剩背景
    assert (_box(frame) == _box(renderer.background)).all()


def test_stills_still_draw_progress_bar(tmp_path: Path) -> None:
    renderer = _renderer(tmp_path)
    t = _mid(renderer.timeline)
    frame = renderer.render(t)  # 預設：靜態圖照舊畫進度條
    assert not (_box(frame) == _box(renderer.background)).all()
    assert _gold_ratio(_box(frame)) > 0


def test_progress_strip_fill(tmp_path: Path) -> None:
    timeline = _renderer(tmp_path).timeline
    x, y, w, h = progress_box(DEFAULT_STYLE)
    start = progress_strip(timeline, DEFAULT_STYLE, 0.0)
    assert start.mode == "RGBA" and start.size == (w, h)
    assert _gold_ratio(np.asarray(start).astype(int)) == 0
    half = progress_strip(timeline, DEFAULT_STYLE, timeline.total / 2)
    assert abs(_gold_ratio(np.asarray(half).astype(int)) - 0.5) < 0.02
    end = progress_strip(timeline, DEFAULT_STYLE, timeline.total)
    assert _gold_ratio(np.asarray(end).astype(int)) > 0.98
    # 進度條以外的地方是透明的，疊上去不會蓋掉畫面
    assert np.asarray(start)[..., 3].min() == 0


def test_strip_overlaid_on_segment_frame_matches_still(tmp_path: Path) -> None:
    renderer = _renderer(tmp_path)
    t = _mid(renderer.timeline)
    x, y, _, _ = progress_box(DEFAULT_STYLE)
    composed = renderer.render(t, progress=False).convert("RGBA")
    composed.alpha_composite(progress_strip(renderer.timeline, DEFAULT_STYLE, t), (x, y))
    # 疊上進度條後，和直接畫進度條的靜態圖一樣（容許半透明混色的四捨五入）
    difference = np.abs(_box(composed) - _box(renderer.render(t)))
    assert difference.max() <= 2


class FakeRecordingRenderer(Renderer):
    """手寫的 fake：照常畫圖，記下每次 render 是否要求畫進度條。"""

    progress_flags: list[bool]

    def render(self, t: float, progress: bool = True) -> Image.Image:
        self.progress_flags.append(progress)
        return super().render(t, progress=progress)


def test_encoder_renders_segments_without_progress(tmp_path: Path) -> None:
    video = load_video(write_game(tmp_path / "game", base_data()))
    timeline = build_timeline(video, lambda beat: 3.0, DEFAULT_STYLE)
    layouts = layout_video(video, FONTS, DEFAULT_STYLE)
    renderer = FakeRecordingRenderer(video, timeline, layouts, FONTS, DEFAULT_STYLE)
    renderer.progress_flags = []
    encoder = FfmpegSegmentEncoder(Ffmpeg(fake_ffmpeg(tmp_path / "bin")), DEFAULT_STYLE)
    encoder.encode(timeline.segments[0], renderer, tmp_path / "s1.mp4")
    assert renderer.progress_flags and not any(renderer.progress_flags)


# --- 整支影片：串接後疊上進度條 ---


def _render_video(tmp_path: Path, command: list[str]):
    from app.integrations.tts import FakeTTSProvider
    from app.integrations.video.pipeline import render_video

    video = load_video(write_game(tmp_path / "game", base_data()))
    return render_video(
        video,
        tmp_path / "game" / "out",
        FONTS,
        DEFAULT_STYLE,
        FakeTTSProvider(),
        Ffmpeg(command),
        cache_dir=tmp_path / "game" / "cache",
    )


def test_pipeline_overlays_progress_after_concat(tmp_path: Path) -> None:
    command = fake_ffmpeg(tmp_path / "bin")
    result = _render_video(tmp_path, command)
    calls = fake_ffmpeg_calls(command)
    concat = next(i for i, c in enumerate(calls) if " concat " in f" {c} ")
    overlay = next(i for i, c in enumerate(calls) if "overlay=" in c)
    mix = next(i for i, c in enumerate(calls) if "sidechaincompress" in c or "loudnorm" in c)
    assert concat < overlay < mix
    # 疊加的輸入是串接好的影片，輸出是無聲版；混音用的是疊好進度條的無聲版
    assert str(result.joined) in calls[overlay] and str(result.silent) in calls[overlay]
    assert str(result.silent) in calls[mix]
    # 逐格送進去的進度條：總格數 × 進度條大小 × RGBA
    timeline_frames = sum(
        len(frame_times(seg, DEFAULT_STYLE.fps)) for seg in _timeline(tmp_path).segments
    )
    _, _, w, h = progress_box(DEFAULT_STYLE)
    expected = timeline_frames * w * h * 4
    assert result.silent.read_bytes() == f"fake-media {expected}".encode()


def _timeline(tmp_path: Path) -> Timeline:
    from app.integrations.tts import FakeTTSProvider
    from app.integrations.video.narration import prepare_narration

    video = load_video(tmp_path / "game")
    clips = prepare_narration(video, FakeTTSProvider(), tmp_path / "game" / "cache")
    return build_timeline(video, lambda beat: clips[beat.beat_key].seconds, DEFAULT_STYLE)


def test_overlay_failure_leaves_no_output(tmp_path: Path) -> None:
    command = fake_ffmpeg(tmp_path / "bin", fail_on="rgba")  # 只有疊加這一步用 rgba
    with pytest.raises(VideoRenderError) as exc:
        _render_video(tmp_path, command)
    assert "進度條" in str(exc.value)
    out = tmp_path / "game" / "out"
    for name in ("silent.tmp.mp4", "silent.mp4", "fake_game.mp4"):
        assert not (out / name).exists(), name


def test_report_has_no_stage_one_limit_note(tmp_path: Path) -> None:
    result = _render_video(tmp_path, fake_ffmpeg(tmp_path / "bin"))
    report = result.report.read_text(encoding="utf-8")
    assert "第 1 階段" not in report
    assert "進度條" in report  # 說明進度條是串接後疊上去的，以及疊加的編碼設定
