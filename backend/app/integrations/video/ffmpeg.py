"""ffmpeg 呼叫（spec media-integrations「ffmpeg 呼叫」）。

影片編碼、串接與混音只在這裡用 subprocess 呼叫 ffmpeg。指令是一個字串陣列，
平常是 [FFMPEG_PATH]；測試可以換成手寫的假指令稿（[python, fake_ffmpeg.py]）。
"""

import shutil
import subprocess
from pathlib import Path
from typing import IO

from app.integrations.video.errors import VideoRenderError, VideoTimeoutError

STDERR_TAIL_LINES = 8


class Ffmpeg:
    def __init__(self, command: list[str], *, timeout_seconds: float | None = None) -> None:
        """timeout_seconds：每次呼叫 ffmpeg 的上限（秒），超過就結束子程序並拋錯；None＝不限。

        背景工作（產生影片）一定要設，避免 ffmpeg 卡住時整個工作停住（add-rules-video-mobile D15）。
        """
        if not command:
            raise ValueError("ffmpeg 指令不能是空的")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    def check(self) -> None:
        """在開始渲染前確認找得到 ffmpeg；找不到時說明要安裝或設定 FFMPEG_PATH。"""
        exe = self.command[0]
        if shutil.which(exe) is None and not Path(exe).is_file():
            raise VideoRenderError(
                f"找不到 ffmpeg（{exe}）：請安裝 ffmpeg（Windows：winget install ffmpeg），"
                "或在 .env 設定 FFMPEG_PATH 指向 ffmpeg 執行檔"
            )

    def run(self, args: list[str], *, what: str) -> None:
        """執行一次 ffmpeg；失敗時拋 VideoRenderError，訊息含 ffmpeg 輸出的最後幾行。"""
        try:
            result = subprocess.run(
                [*self.command, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise self.timeout_error(what) from exc
        if result.returncode != 0:
            raise VideoRenderError(f"ffmpeg {what}失敗：\n{stderr_tail(result.stderr)}")

    def popen(self, args: list[str], stderr: IO[bytes]) -> subprocess.Popen[bytes]:
        """開一個從標準輸入讀資料的 ffmpeg（逐格畫面用）。stderr 寫到檔案，避免管線塞滿卡住。"""
        return subprocess.Popen(
            [*self.command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        )

    def timeout_error(self, what: str) -> VideoTimeoutError:
        return VideoTimeoutError(f"ffmpeg {what}超過 {self.timeout_seconds:g} 秒沒有完成，已停止")


def stderr_tail(data: bytes, lines: int = STDERR_TAIL_LINES) -> str:
    text = data.decode("utf-8", errors="replace").strip()
    return "\n".join(text.splitlines()[-lines:]) or "（ffmpeg 沒有輸出錯誤訊息）"
