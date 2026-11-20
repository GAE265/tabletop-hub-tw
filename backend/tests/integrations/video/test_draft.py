"""草稿模式（spec rules-video-script「草稿模式」）。"""

from pathlib import Path
from typing import Any

import pytest

from app.integrations.video import VideoDataError, load_video
from tests.integrations.video.support import base_data, segment, write_game


def draft_data() -> dict[str, Any]:
    """預設假遊戲改成草稿：blue 待拍、zone_a 待量測，另外列一個繪製的骰子。"""
    data = base_data()
    data["assets"][2]["file"] = None  # blue
    data["assets"][3]["regions"]["zone_a"] = None  # board 的 zone_a
    data["assets"].append(
        {
            "asset_key": "die",
            "kind": "drawn",
            "priority": "optional",
            "reason": "viewer may see the die",
        }
    )
    return data


def test_draft_allows_pending_photo_and_region(tmp_path: Path) -> None:
    video = load_video(write_game(tmp_path, draft_data()), draft=True)
    assert video.assets["blue"].file is None
    assert video.assets["board"].regions["zone_a"] is None
    assert video.assets["board"].regions["zone_b"] is not None


def test_draft_allows_drawn_asset(tmp_path: Path) -> None:
    video = load_video(write_game(tmp_path, draft_data()), draft=True)
    assert video.assets["die"].kind == "drawn"


def test_formal_mode_lists_what_is_missing(tmp_path: Path) -> None:
    folder = write_game(tmp_path, draft_data())
    with pytest.raises(VideoDataError) as exc:
        load_video(folder)
    message = str(exc.value)
    assert "blue" in message and "待拍" in message
    assert "zone_a" in message and "待量測" in message
    assert "die" in message and "drawn" in message


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda d: segment(d, "s2")["slots"]["main"].__setitem__("asset_key", "ghost"), "ghost"),
        (
            lambda d: segment(d, "s1")["beats"][0]["cues"].append(
                {"at": 0, "do": "fly", "target": "main"}
            ),
            "fly",
        ),
    ],
    ids=["unknown-asset", "unknown-action"],
)
def test_draft_still_rejects_other_errors(tmp_path: Path, mutate, expected: str) -> None:
    data = draft_data()
    mutate(data)
    with pytest.raises(VideoDataError) as exc:
        load_video(write_game(tmp_path, data), draft=True)
    assert expected in str(exc.value)
