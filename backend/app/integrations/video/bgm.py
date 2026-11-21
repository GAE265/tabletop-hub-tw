"""程式合成的背景音樂（依《血與刃》製作紀錄第 7 節）。

和弦鋪墊、持續低音、音樂盒式鈴聲、風聲、章開頭的低沉重擊，加上殘響、淡入淡出與軟削波。
長度等於影片總長；固定亂數種子，同樣的長度與章的位置得到完全相同的音樂。
"""

import io
import wave

import numpy as np
from scipy import signal

SAMPLE_RATE = 48000
PEAK = 0.89
DEFAULT_SEED = 20261120

# 音名 → 頻率（Hz）
_NOTE = {
    "F2": 87.31, "G2": 98.00, "A2": 110.00, "Bb2": 116.54,
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00,
    "D5": 587.33, "F5": 698.46, "G5": 783.99, "A5": 880.00, "C6": 1046.50,
}  # fmt: skip
_CHORDS = {
    "Dm": ("D3", "F3", "A3"),
    "Bb": ("Bb2", "D3", "F3"),
    "Gm": ("G2", "Bb2", "D3"),
    "A": ("A2", "C#3", "E3"),
    "F": ("F2", "A2", "C3"),
    "C": ("C3", "E3", "G3"),
}
_PROGRESSION = (
    "Dm", "Bb", "Gm", "A", "Dm", "Bb", "Gm", "A",
    "Dm", "F", "C", "A", "Gm", "Bb", "A", "Dm",
)  # fmt: skip
_BELL_NOTES = ("D5", "F5", "G5", "A5", "C6")


def synthesize_bgm(
    seconds: float, chapter_starts: tuple[float, ...] = (), seed: int = DEFAULT_SEED
) -> np.ndarray:
    """回傳 (樣本數, 2) 的 float32 立體聲，範圍在 ±PEAK 內，開頭與結尾為靜音。"""
    n = max(1, round(seconds * SAMPLE_RATE))
    t = np.arange(n) / SAMPLE_RATE
    rng = np.random.default_rng(seed)
    mix = np.zeros((n, 2))

    _add_pad(mix, t, seconds, rng)
    _add_drone(mix, t)
    _add_bells(mix, t, seconds, rng)
    _add_wind(mix, t, rng)
    for start in chapter_starts:
        _add_boom(mix, start, rng)

    mix = _reverb(mix, rng)
    mix = signal.sosfiltfilt(
        signal.butter(2, 80, "highpass", fs=SAMPLE_RATE, output="sos"), mix, axis=0
    )
    mix *= _fades(n, seconds)[:, None]
    mix = np.tanh(mix * 1.5)
    loudest = float(np.max(np.abs(mix)))
    if loudest > 0:
        mix *= PEAK / loudest
    return mix.astype(np.float32)


def to_wav(audio: np.ndarray) -> bytes:
    """float 立體聲 → 16-bit PCM wav。"""
    pcm = np.clip(audio, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _envelope(length: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(length)
    a, r = min(length, int(attack * SAMPLE_RATE)), min(length, int(release * SAMPLE_RATE))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def _pan(mono: np.ndarray, position: float) -> np.ndarray:
    """position：-1 左、0 中、1 右（等功率）。"""
    angle = (position + 1) * np.pi / 4
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)


def _add_pad(mix: np.ndarray, t: np.ndarray, seconds: float, rng: np.random.Generator) -> None:
    """16 個和弦鋪墊：每個音由三個略為失諧的正弦波加泛音疊成，再低通。"""
    n = len(t)
    pad = np.zeros((n, 2))
    span = seconds / len(_PROGRESSION)
    for index, name in enumerate(_PROGRESSION):
        start = int(index * span * SAMPLE_RATE)
        end = min(n, int((index + 1) * span * SAMPLE_RATE) + int(min(2.0, span) * SAMPLE_RATE))
        if start >= n:
            break
        local = t[start:end]
        env = _envelope(end - start, min(4.5, span * 0.6), min(5.5, span * 0.8))
        for note in _CHORDS[name]:
            freq = _NOTE[note]
            tone = np.zeros_like(local)
            for detune in (-0.6, 0.0, 0.6):
                for harmonic in range(1, 5):
                    tone += np.sin(2 * np.pi * (freq + detune) * harmonic * local) / harmonic**2
            pad[start:end] += _pan(tone * env * 0.05, rng.uniform(-0.6, 0.6))
    sos = signal.butter(2, 1000, "lowpass", fs=SAMPLE_RATE, output="sos")
    mix += signal.sosfiltfilt(sos, pad, axis=0)


def _add_drone(mix: np.ndarray, t: np.ndarray) -> None:
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.06 * t)
    drone = sum(np.sin(2 * np.pi * _f * t) for _f in (36.71, 73.42, 110.00, 146.83))
    mix += _pan(drone * lfo * 0.03, 0.0)


def _add_bells(mix: np.ndarray, t: np.ndarray, seconds: float, rng: np.random.Generator) -> None:
    """音樂盒式 FM 鈴聲：約 28% 機率彈三個音的小旋律，其餘為單音，間隔 3 到 9 秒。"""
    n = len(t)
    clock = rng.uniform(1.5, 4.0)
    while clock < seconds - 1.0:
        notes = (
            list(rng.choice(_BELL_NOTES, size=3))
            if rng.random() < 0.28
            else [rng.choice(_BELL_NOTES)]
        )
        for k, note in enumerate(notes):
            start = int((clock + k * 0.35) * SAMPLE_RATE)
            length = min(n - start, int(2.5 * SAMPLE_RATE))
            if length <= 0:
                continue
            local = np.arange(length) / SAMPLE_RATE
            freq = _NOTE[str(note)]
            index = 3.0 * np.exp(-local / 0.6)
            tone = np.sin(2 * np.pi * freq * local + index * np.sin(2 * np.pi * freq * 3.5 * local))
            tone *= np.exp(-local / 0.8) * 0.06
            mix[start : start + length] += _pan(tone, rng.uniform(-0.5, 0.5))
        clock += rng.uniform(3.0, 9.0)


def _add_wind(mix: np.ndarray, t: np.ndarray, rng: np.random.Generator) -> None:
    noise = rng.standard_normal((len(t), 2))
    sos = signal.butter(2, [250, 900], "bandpass", fs=SAMPLE_RATE, output="sos")
    wind = signal.sosfiltfilt(sos, noise, axis=0)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t + 1.3)
    mix += wind * lfo[:, None] * 0.004


def _add_boom(mix: np.ndarray, start_sec: float, rng: np.random.Generator) -> None:
    """低沉重擊：頻率從 90 Hz 掉到 44 Hz，約 3 秒，只放在章的開頭。"""
    n = len(mix)
    start = int(start_sec * SAMPLE_RATE)
    length = min(n - start, 3 * SAMPLE_RATE)
    if length <= 0:
        return
    local = np.arange(length) / SAMPLE_RATE
    freq = 44 + 46 * np.exp(-local / 0.5)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    boom = np.sin(phase) * np.exp(-local / 0.9)
    noise = signal.sosfiltfilt(
        signal.butter(2, 120, "lowpass", fs=SAMPLE_RATE, output="sos"), rng.standard_normal(length)
    )
    boom = (boom + noise * 0.3) * 0.25
    mix[start : start + length] += _pan(boom, 0.0)


def _reverb(mix: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """用衰減的雜訊脈衝響應做捲積殘響（約 5 秒衰減，越尾端越暗）。"""
    length = int(2.5 * SAMPLE_RATE)
    decay = np.exp(-np.arange(length) / SAMPLE_RATE / 0.9)
    wet = np.zeros_like(mix)
    sos = signal.butter(1, 3000, "lowpass", fs=SAMPLE_RATE, output="sos")
    for channel in range(2):
        impulse = signal.sosfilt(sos, rng.standard_normal(length)) * decay
        impulse /= np.sqrt(np.sum(impulse**2))
        wet[:, channel] = signal.fftconvolve(mix[:, channel], impulse)[: len(mix)]
    return mix * 0.75 + wet * 0.35


def _fades(n: int, seconds: float) -> np.ndarray:
    """片頭淡入、片尾淡出（短影片時依長度縮短），頭尾都從 0 開始、到 0 結束。"""
    gain = np.ones(n)
    fade_in = max(1, min(n // 2, int(min(3.0, seconds / 4) * SAMPLE_RATE)))
    fade_out = max(1, min(n // 2, int(min(7.0, seconds / 3) * SAMPLE_RATE)))
    gain[:fade_in] = np.linspace(0, 1, fade_in) ** 2
    gain[-fade_out:] *= np.linspace(1, 0, fade_out) ** 2
    return gain
