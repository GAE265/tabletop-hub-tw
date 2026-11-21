"""影片整合層的例外。不帶 HTTP 狀態碼，由呼叫方決定怎麼回報。"""


class VideoError(Exception):
    """基底類別。"""


class VideoDataError(VideoError):
    """段資料格式錯誤：一次列出所有找到的錯誤，訊息指出哪一段、哪一句、哪個欄位。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        lines = "\n".join(f"- {error}" for error in self.errors)
        super().__init__(f"段資料有 {len(self.errors)} 個錯誤：\n{lines}")


class LayoutError(VideoError):
    """排版失敗，例如文字縮到最小字級仍放不下。"""


class FontConfigError(VideoError):
    """字型設定錯誤：檔案不存在或字型集合的 index 超出範圍。訊息指出是哪一個設定。"""


class VideoRenderError(VideoError):
    """渲染或編碼失敗。"""


class VideoTimeoutError(VideoRenderError):
    """ffmpeg 超過 timeout_seconds 沒有完成，已結束子程序。"""
