"""先音後畫的時間軸（spec rules-video-maker「先音後畫的時間軸」）。

先取得每句旁白的長度，再算出每句、每段、每個 cue 的絕對秒數。
句長 = max(min_beat_sec, pad_before + 旁白長度 + pad_after, 最後一個 cue 結束 + cue_hold)，
所以旁白不會超出時段、動作不會被下一句切掉；改了某一句，後面的時間自動重算。
結果只寫進時間報表，不回寫段資料。
"""

import csv
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.integrations.video.model import Beat, Cue, Segment, Video
from app.integrations.video.style import Style
from app.integrations.video.templates import TEMPLATES

NarrationSeconds = Callable[[Beat], float]


def estimate_narration_seconds(text: str) -> float:
    """沒有實際合成旁白時的估計長度：每 4 個字 1 秒，至少 1 秒（與 fake TTS 相同的算法）。"""
    chars = len("".join(text.split()))
    return max(1.0, chars / 4)


def cue_seconds(cue: Cue, style: Style) -> float:
    """動作本身需要的秒數；數值放在風格設定。"""
    if cue.do == "show":
        return style.fade_seconds if cue.anim == "fade" else style.pop_seconds
    if cue.do == "hide":
        return style.hide_seconds
    if cue.do == "flip":
        return style.flip_seconds
    if cue.do == "move":
        return style.move_seconds
    return cue.duration or style.shuffle_seconds  # shuffle


@dataclass(frozen=True)
class CueTiming:
    cue: Cue
    start: float  # 全片的絕對秒數
    end: float


@dataclass(frozen=True)
class BeatTiming:
    beat: Beat
    segment_key: str
    start: float
    duration: float
    audio_sec: float
    cues: tuple[CueTiming, ...]

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class SegmentTiming:
    segment: Segment
    start: float
    duration: float
    beats: tuple[BeatTiming, ...]

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class Timeline:
    segments: tuple[SegmentTiming, ...]
    total: float
    # 每章的開始與結束秒數，依章的順序（進度條用）
    chapter_spans: tuple[tuple[str, float, float], ...]

    def segment_at(self, t: float) -> SegmentTiming:
        for seg in self.segments:
            if t < seg.end:
                return seg
        return self.segments[-1]


def beat_seconds(beat: Beat, audio_sec: float, segment: Segment, style: Style) -> float:
    timing = segment.timing
    narration = timing.pad_before + audio_sec + timing.pad_after
    last_cue = max((c.at + cue_seconds(c, style) for c in beat.cues), default=0.0)
    cues = last_cue + timing.cue_hold if beat.cues else 0.0
    return max(timing.min_beat_sec, narration, cues)


def build_timeline(video: Video, narration_seconds: NarrationSeconds, style: Style) -> Timeline:
    segments = []
    clock = 0.0
    for segment in video.segments:
        spec = TEMPLATES[segment.template]
        seg_start = clock
        beats = []
        if spec.fixed_seconds is not None:
            clock += spec.fixed_seconds
        else:
            for beat in segment.beats:
                audio = narration_seconds(beat)
                duration = beat_seconds(beat, audio, segment, style)
                cues = tuple(
                    CueTiming(c, clock + c.at, clock + c.at + cue_seconds(c, style))
                    for c in beat.cues
                )
                beats.append(BeatTiming(beat, segment.segment_key, clock, duration, audio, cues))
                clock += duration
        segments.append(SegmentTiming(segment, seg_start, clock - seg_start, tuple(beats)))

    spans: list[tuple[str, float, float]] = []
    for seg in segments:
        key = seg.segment.chapter_key
        if spans and spans[-1][0] == key:
            spans[-1] = (key, spans[-1][1], seg.end)
        else:
            spans.append((key, seg.start, seg.end))
    return Timeline(tuple(segments), clock, tuple(spans))


def write_timing_csv(timeline: Timeline, path: Path) -> None:
    """時間報表（UTF-8 BOM），格式接近手做版的 narration.csv，方便比對。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["segment_key", "beat_key", "start_sec", "beat_sec", "audio_sec", "chars", "subtitle"]
        )
        for seg in timeline.segments:
            for beat in seg.beats:
                pad = seg.segment.timing.pad_before
                writer.writerow(
                    [
                        seg.segment.segment_key,
                        beat.beat.beat_key,
                        f"{beat.start + pad:.2f}",
                        f"{beat.duration:.2f}",
                        f"{beat.audio_sec:.2f}",
                        len("".join(beat.beat.narration.split())),
                        beat.beat.subtitle,
                    ]
                )
