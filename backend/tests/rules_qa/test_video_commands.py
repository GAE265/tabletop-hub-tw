"""規則影片的本機指令 check、stills（spec rules-video-maker「本機指令與靜態圖」）。

不連資料庫、不需要 ffmpeg 與金鑰；字型未設定時用 Pillow 內建字型。
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import Settings
from app.domains.rules_qa.video_commands import main
from app.integrations.llm.errors import LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.video import load_video
from tests.integrations.video.support import (
    base_data,
    fake_ffmpeg,
    fake_ffmpeg_calls,
    segment,
    write_game,
)
from tests.rules_qa.video_script_support import llm_output, write_inputs

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


# --- draft、compare（1c）：用 FakeLLMProvider，不連真正的 LLM ---


def _draft_args(folder: Path, *extra: str) -> list[str]:
    return [
        "draft", str(folder),
        "--pages", "rulebook/en-005.txt",
        "--chapter-number", "11", "--chapter-title", "步驟三",
        *extra,
    ]  # fmt: skip


def test_draft_writes_separate_file(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    hand_before = (folder / "video.json").read_text(encoding="utf-8")
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    code = main(_draft_args(folder), settings=make_settings(), llm=llm)
    assert code == 0, capsys.readouterr().err
    draft = load_video(folder / "draft", draft=True)
    assert len(draft.segments) == 2
    assert (folder / "video.json").read_text(encoding="utf-8") == hand_before


def test_draft_missing_inputs_does_not_call_llm(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_game(tmp_path / "game", base_data())  # 沒有 rulebook/ 與 terms.json
    llm = FakeLLMProvider(json_outputs=[])
    code = main(_draft_args(folder), settings=make_settings(), llm=llm)
    assert code != 0
    assert "en-005.txt" in capsys.readouterr().err
    assert llm.calls == []
    assert not (folder / "draft").exists()


def test_draft_llm_unavailable(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    llm = FakeLLMProvider(json_outputs=[LLMUnavailable("連不上")])
    code = main(_draft_args(folder), settings=make_settings(), llm=llm)
    assert code != 0
    assert "LLM" in capsys.readouterr().err
    assert not (folder / "draft" / "video.json").exists()


def test_draft_rejected_keeps_raw_outputs(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    bad = llm_output()
    bad["segments"][0]["beats"][0]["narration"] = "每次都洗牌。"
    code = main(
        _draft_args(folder), settings=make_settings(), llm=FakeLLMProvider(json_outputs=[bad, bad])
    )
    assert code != 0
    assert "次" in capsys.readouterr().err
    assert not (folder / "draft" / "video.json").exists()
    for n in (1, 2):
        assert (folder / "draft" / f"rejected-{n}.json").is_file()


def test_draft_assets_from_hand_version(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    output = llm_output()
    output["assets"].append(
        {"asset_key": "dice", "kind": "drawn", "priority": "optional",
         "reason": "骰子", "shot": "繪製一顆骰子", "regions": []}
    )  # fmt: skip
    code = main(
        _draft_args(folder, "--assets-from", "video.json"),
        settings=make_settings(),
        llm=FakeLLMProvider(json_outputs=[output]),
    )
    assert code == 0, capsys.readouterr().err
    draft = load_video(folder / "draft", draft=True)
    assert draft.assets["board"].file == "board.png"
    assert (folder / "draft" / "assets" / "board.png").is_file()
    assert draft.assets["board"].regions["zone_a"] is not None
    assert draft.assets["dice"].file is None  # 沒對上的仍待拍


def test_compare_writes_report(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    write_game(tmp_path / "ai", base_data())
    write_game(tmp_path / "hand", base_data())
    code = main(["compare", str(tmp_path / "ai"), str(tmp_path / "hand")], settings=make_settings())
    assert code == 0, capsys.readouterr().err
    assert "摘要" in (tmp_path / "ai" / "compare.md").read_text(encoding="utf-8")


def test_compare_invalid_file(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    write_game(tmp_path / "ai", base_data())
    bad = base_data()
    segment(bad, "s2")["slots"]["main"]["asset_key"] = "ghost"
    write_game(tmp_path / "hand", bad)
    code = main(["compare", str(tmp_path / "ai"), str(tmp_path / "hand")], settings=make_settings())
    assert code != 0
    err = capsys.readouterr().err
    assert "hand" in err and "ghost" in err
    assert not (tmp_path / "ai" / "compare.md").exists()


def test_draft_missing_reference_page_does_not_call_llm(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    llm = FakeLLMProvider(json_outputs=[])
    args = _draft_args(folder, "--reference-pages", "rulebook/en-099.txt")
    code = main(args, settings=make_settings(), llm=llm)
    assert code != 0
    assert "en-099.txt" in capsys.readouterr().err
    assert llm.calls == []


def test_draft_with_reference_pages(
    tmp_path: Path, make_settings: Callable[..., Settings], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = write_inputs(write_game(tmp_path / "game", base_data()))
    llm = FakeLLMProvider(json_outputs=[llm_output()])
    args = _draft_args(folder, "--reference-pages", "rulebook/en-003.txt")
    code = main(args, settings=make_settings(), llm=llm)
    assert code == 0, capsys.readouterr().err
    assert "Red Knight" in llm.calls[0].kwargs["input"]
