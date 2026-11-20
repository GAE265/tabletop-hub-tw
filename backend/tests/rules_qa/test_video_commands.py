"""規則影片的本機指令 check、stills（spec rules-video-maker「本機指令與靜態圖」）。

不連資料庫、不需要 ffmpeg 與金鑰；字型未設定時用 Pillow 內建字型。
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import Settings
from app.domains.rules_qa.video_commands import main
from tests.integrations.video.support import (
    base_data,
    fake_ffmpeg,
    fake_ffmpeg_calls,
    segment,
    write_game,
)

Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run(make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]) -> Run:
    def _run(*args: str, **settings: object) -> tuple[int, str, str]:
        code = main(list(args), settings=make_settings(**settings))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def test_check_ok(tmp_path: Path, run: Run) -> None:
    write_game(tmp_path, base_data())
    code, out, _ = run("check", str(tmp_path))
    assert code == 0
    assert "2 段" in out and "3 句" in out and "4 個素材" in out


def test_stills_outputs(tmp_path: Path, run: Run) -> None:
    write_game(tmp_path, base_data())
    code, _, _ = run("stills", str(tmp_path))
    assert code == 0
    stills = sorted((tmp_path / "out" / "stills").glob("*.png"))
    # 3 句各一張＋4 個 cue 各一張
    assert len(stills) == 7
    for path in stills:
        with Image.open(path) as image:
            assert image.size == (1920, 1080)
    assert (tmp_path / "out" / "sheet.png").is_file()
    assert (tmp_path / "out" / "timing.csv").is_file()


def test_stills_without_font_warns(tmp_path: Path, run: Run) -> None:
    write_game(tmp_path, base_data())
    code, _, err = run("stills", str(tmp_path))
    assert code == 0
    assert "未設定中文字型" in err


def test_missing_font_file_rejected(tmp_path: Path, run: Run) -> None:
    write_game(tmp_path, base_data())
    code, _, err = run(
        "stills", str(tmp_path), video_font_regular=str(tmp_path / "no-such-font.ttc")
    )
    assert code != 0
    assert "VIDEO_FONT_REGULAR" in err
    assert not (tmp_path / "out" / "stills").exists()


@pytest.mark.parametrize("command", ["check", "stills"])
def test_invalid_data_no_output(tmp_path: Path, run: Run, command: str) -> None:
    data = base_data()
    segment(data, "s2")["slots"]["main"]["asset_key"] = "ghost"
    write_game(tmp_path, data)
    code, _, err = run(command, str(tmp_path))
    assert code != 0
    assert "ghost" in err
    assert not (tmp_path / "out").exists()


# --- render（MR 3）：用手寫的假 ffmpeg，不需要安裝 ffmpeg ---


def test_render_with_fake_tts_warns_estimated_time(
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_game(tmp_path / "game", base_data())
    ffmpeg = fake_ffmpeg(tmp_path / "bin")
    code = main(["render", str(tmp_path / "game")], settings=make_settings(), ffmpeg=ffmpeg)
    err = capsys.readouterr().err
    assert code == 0
    assert "旁白為靜音" in err and "時間為估計值" in err
    out = tmp_path / "game" / "out"
    assert (out / "fake_game.mp4").is_file()
    assert (out / "timing.csv").is_file()
    assert "時間為估計值" in (out / "report.txt").read_text(encoding="utf-8")
    # 編碼 2 段、串接、混音
    calls = fake_ffmpeg_calls(ffmpeg)
    assert len(calls) == 4
    assert any("sidechaincompress" in call for call in calls)


def test_render_invalid_data_no_output(
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = base_data()
    segment(data, "s2")["slots"]["main"]["asset_key"] = "ghost"
    write_game(tmp_path / "game", data)
    ffmpeg = fake_ffmpeg(tmp_path / "bin")
    code = main(["render", str(tmp_path / "game")], settings=make_settings(), ffmpeg=ffmpeg)
    assert code != 0
    assert "ghost" in capsys.readouterr().err
    assert not (tmp_path / "game" / "out").exists()
    assert not (tmp_path / "game" / "cache").exists()  # 沒有呼叫 TTS
    assert fake_ffmpeg_calls(ffmpeg) == []


def test_render_missing_ffmpeg_fails_before_tts(
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_game(tmp_path / "game", base_data())
    settings = make_settings(ffmpeg_path=str(tmp_path / "no-such-ffmpeg.exe"))
    code = main(["render", str(tmp_path / "game")], settings=settings)
    assert code != 0
    assert "FFMPEG_PATH" in capsys.readouterr().err
    assert not (tmp_path / "game" / "cache").exists()
