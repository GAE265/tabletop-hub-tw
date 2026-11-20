"""影片段資料測試共用的假遊戲（spec rules-video-maker）。

只用程式產生的純色小圖片與英數文字，不含任何真實遊戲的素材或規則書內容。
預設資料：2 段、3 句、4 個 cue（第 1 段有一排三張牌＋側欄盤面，第 2 段一張圖）。
"""

import copy
import json
from pathlib import Path
from typing import Any

from PIL import Image

CARD_SIZE = (100, 160)
BOARD_SIZE = (300, 300)

_BASE: dict[str, Any] = {
    "format_version": 1,
    "game_key": "fake_game",
    "title": "Fake Game Rules",
    "chapters": [{"chapter_key": "c1", "number": 1, "title": "Step One"}],
    "assets": [
        {
            "asset_key": "back",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "cards are face down",
            "file": "back.png",
        },
        {
            "asset_key": "red",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "viewer must read the red card",
            "file": "red.png",
        },
        {
            "asset_key": "blue",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "viewer must read the blue card",
            "file": "blue.png",
        },
        {
            "asset_key": "board",
            "kind": "flat_photo",
            "priority": "must",
            "reason": "viewer must see where cards go",
            "file": "board.png",
            "regions": {"zone_a": [0.0, 0.0, 0.5, 0.5], "zone_b": [0.5, 0.5, 0.5, 0.5]},
        },
    ],
    "segments": [
        {
            "segment_key": "s1",
            "chapter_key": "c1",
            "source_pages": [{"lang": "en", "page": 5}],
            "slots": {
                "main_title": {"kind": "text", "text": "Case 1", "hidden": True},
                "main": {
                    "kind": "items",
                    "items": [
                        {"item_key": "c1", "asset_key": "red", "back_asset_key": "back"},
                        {"item_key": "c2", "asset_key": "blue", "back_asset_key": "back"},
                        {"item_key": "c3", "asset_key": "red", "back_asset_key": "back"},
                    ],
                },
                "sidebar": {"kind": "asset", "asset_key": "board"},
            },
            "highlights": [
                {"key": "h1", "target": "sidebar@zone_a", "shape": "box", "style": "gold"}
            ],
            "labels": [
                {
                    "key": "l1",
                    "text": "remove",
                    "target": "main.c2",
                    "position": "below",
                    "style": "plain",
                }
            ],
            "beats": [
                {
                    "beat_key": "b1",
                    "narration": "a" * 12,
                    "subtitle": "Shuffle and flip the cards.",
                    "cues": [
                        {"at": 0.5, "do": "flip", "target": "main"},
                        {"at": 1.6, "do": "show", "target": "main_title"},
                    ],
                },
                {
                    "beat_key": "b2",
                    "narration": "b" * 12,
                    "subtitle": "Remove the blue card.",
                    "cues": [
                        {"at": 0.5, "do": "hide", "target": "main.c2"},
                        {"at": 1.0, "do": "move", "target": "main.c1", "to": "sidebar@zone_a"},
                    ],
                },
            ],
        },
        {
            "segment_key": "s2",
            "chapter_key": "c1",
            "source_pages": [{"lang": "en", "page": 6}],
            "slots": {"main": {"kind": "asset", "asset_key": "red"}},
            "beats": [{"beat_key": "b3", "narration": "c" * 12, "subtitle": "Done."}],
        },
    ],
}

_COLORS = {
    "back.png": (40, 40, 60),
    "red.png": (200, 40, 40),
    "blue.png": (40, 60, 200),
    "board.png": (90, 80, 60),
}


def base_data() -> dict[str, Any]:
    """預設假遊戲資料的複本，測試可以直接修改。"""
    return copy.deepcopy(_BASE)


def segment(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next(s for s in data["segments"] if s["segment_key"] == key)


def write_game(
    folder: Path, data: dict[str, Any], sizes: dict[str, tuple[int, int]] | None = None
) -> Path:
    """把段資料與素材圖片寫進 folder，回傳 folder。sizes 可以指定某個檔案的尺寸。"""
    sizes = sizes or {}
    assets_dir = folder / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in data.get("assets", []):
        name = asset.get("file")
        if not name:
            continue
        size = sizes.get(name, BOARD_SIZE if name == "board.png" else CARD_SIZE)
        Image.new("RGB", size, _COLORS.get(name, (120, 120, 120))).save(assets_dir / name)
    (folder / "video.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return folder


FAKE_FFMPEG_OK = r"""
import sys
# 假 ffmpeg：讀完標準輸入（逐格畫面），在最後一個參數的路徑寫一個假檔案；記下參數方便測試檢查
data = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
args = sys.argv[1:]
with open(args[-1], "wb") as f:
    f.write(b"fake-media " + str(len(data)).encode())
with open(__file__ + ".log", "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\n")
"""

FAKE_FFMPEG_FAIL = """
import sys
# 假 ffmpeg：不讀輸入，直接印出錯誤並以 1 結束
for n in range(1, 21):
    print(f"log line {n}", file=sys.stderr)
print("fake encoder exploded", file=sys.stderr)
sys.exit(1)
"""


def fake_ffmpeg(folder: Path, *, fail: bool = False) -> list[str]:
    """回傳可以當 ffmpeg 指令使用的命令（python 直譯器＋手寫的假指令稿）。"""
    import sys

    folder.mkdir(parents=True, exist_ok=True)
    script = folder / ("fake_ffmpeg_fail.py" if fail else "fake_ffmpeg.py")
    script.write_text(FAKE_FFMPEG_FAIL if fail else FAKE_FFMPEG_OK, encoding="utf-8")
    return [sys.executable, str(script)]


def fake_ffmpeg_calls(command: list[str]) -> list[str]:
    log = Path(command[-1] + ".log")
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []
