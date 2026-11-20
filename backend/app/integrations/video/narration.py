"""旁白合成與快取（spec rules-video-maker「先音後畫的時間軸」）。

每句旁白用 TTS 合成一次，音檔存在 <cache>/narration/，檔名是「聲音＋文字」的雜湊。
文字與聲音沒變就直接用快取，不重新呼叫 TTS；中途失敗時，已合成的句子保留在快取，下次只補缺的。
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.integrations.tts import TTSProvider
from app.integrations.tts.base import wav_seconds
from app.integrations.video.model import Video


@dataclass(frozen=True)
class NarrationClip:
    path: Path
    seconds: float


def narration_key(voice: str, text: str) -> str:
    return hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()


def prepare_narration(video: Video, tts: TTSProvider, cache_dir: Path) -> dict[str, NarrationClip]:
    """依段的順序合成每一句旁白，回傳 beat_key → 音檔與長度。"""
    folder = cache_dir / "narration"
    folder.mkdir(parents=True, exist_ok=True)
    clips: dict[str, NarrationClip] = {}
    for segment in video.segments:
        for beat in segment.beats:
            path = folder / f"{narration_key(video.voice, beat.narration)}.wav"
            if path.is_file():
                seconds = wav_seconds(path.read_bytes())
            else:
                clip = tts.synthesize(beat.narration, video.voice)
                # 先寫暫存檔再改名，中斷時不會留下壞的快取
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(clip.data)
                temporary.replace(path)
                seconds = clip.seconds
            clips[beat.beat_key] = NarrationClip(path, seconds)
    return clips
