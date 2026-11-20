"""段資料格式與驗證（spec rules-video-maker「段資料格式與驗證」）。"""

from pathlib import Path
from typing import Any

import pytest

from app.integrations.video import VideoDataError, load_video
from tests.integrations.video.support import base_data, segment, write_game


def _load(tmp_path: Path, data: dict[str, Any]):
    return load_video(write_game(tmp_path, data))


def _errors(tmp_path: Path, data: dict[str, Any]) -> str:
    with pytest.raises(VideoDataError) as exc:
        _load(tmp_path, data)
    return str(exc.value)


def test_base_data_loads(tmp_path: Path) -> None:
    video = _load(tmp_path, base_data())
    assert [s.segment_key for s in video.segments] == ["s1", "s2"]
    assert sum(len(s.beats) for s in video.segments) == 3


def test_minimal_segment_loads_with_defaults(tmp_path: Path) -> None:
    data = base_data()
    data["segments"] = [segment(data, "s2")]
    video = _load(tmp_path, data)
    only = video.segments[0]
    assert only.template == "main_with_sidebar"
    assert only.slots["main"].kind == "asset"
    assert only.slots["main"].hidden is False
    assert only.highlights == () and only.labels == ()
    assert only.beats[0].cues == ()
    assert only.transition_in == "cut"
    assert only.timing.min_beat_sec == 2.6


def test_unknown_asset_rejected(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s2")["slots"]["main"]["asset_key"] = "ghost"
    message = _errors(tmp_path, data)
    assert "s2" in message and "main" in message and "ghost" in message


def test_missing_main_rejected(tmp_path: Path) -> None:
    data = base_data()
    del segment(data, "s1")["slots"]["main"]
    # 刪掉 main 之後，指向它的 cue 與 label 也會報錯；這裡只確認缺 main 有被指出
    assert "缺少必填槽位 main" in _errors(tmp_path, data)


def test_unknown_slot_rejected(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s2")["slots"]["footer"] = {"kind": "text", "text": "x"}
    message = _errors(tmp_path, data)
    assert "footer" in message
    for name in ("main_title", "main", "sidebar"):
        assert name in message


def test_slot_kind_mismatch_rejected(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s1")["slots"]["sidebar"] = {
        "kind": "items",
        "items": [{"item_key": "x1", "asset_key": "red"}],
    }
    message = _errors(tmp_path, data)
    assert "sidebar" in message and "asset、text、bullets" in message

    data = base_data()
    segment(data, "s2")["slots"]["main"] = {"kind": "bullets", "items": ["a"]}
    assert "asset、items" in _errors(tmp_path, data)


@pytest.mark.parametrize(
    "mutate, key",
    [
        (lambda d: d["segments"].append(segment(d, "s2") | {}), "s2"),
        (
            lambda d: segment(d, "s2")["beats"].__setitem__(
                0, segment(d, "s2")["beats"][0] | {"beat_key": "b1"}
            ),
            "b1",
        ),
        (lambda d: d["assets"].append(dict(d["assets"][1])), "red"),
        (
            lambda d: segment(d, "s1")["slots"]["main"]["items"].append(
                {"item_key": "c1", "asset_key": "blue"}
            ),
            "c1",
        ),
        (
            lambda d: segment(d, "s1")["highlights"].append(
                dict(segment(d, "s1")["highlights"][0])
            ),
            "h1",
        ),
        (lambda d: segment(d, "s1")["labels"].append(dict(segment(d, "s1")["labels"][0])), "l1"),
    ],
    ids=["segment", "beat", "asset", "item", "highlight", "label"],
)
def test_duplicate_keys_rejected(tmp_path: Path, mutate, key: str) -> None:
    data = base_data()
    mutate(data)
    message = _errors(tmp_path, data)
    assert "重複" in message and key in message


@pytest.mark.parametrize(
    "mutate, missing",
    [
        (
            lambda d: segment(d, "s1")["beats"][0]["cues"].append(
                {"at": 0, "do": "show", "target": "nope"}
            ),
            "nope",
        ),
        (
            lambda d: segment(d, "s1")["highlights"][0].__setitem__("target", "sidebar@zone_z"),
            "sidebar@zone_z",
        ),
        (lambda d: segment(d, "s1")["labels"][0].__setitem__("target", "main.c9"), "main.c9"),
        (
            lambda d: segment(d, "s1")["beats"][1]["cues"][1].__setitem__("to", "sidebar@zone_z"),
            "sidebar@zone_z",
        ),
    ],
    ids=["cue", "highlight", "label", "move-to"],
)
def test_unknown_target_rejected(tmp_path: Path, mutate, missing: str) -> None:
    data = base_data()
    mutate(data)
    message = _errors(tmp_path, data)
    assert "s1" in message and missing in message


def test_flip_without_back_rejected(tmp_path: Path) -> None:
    data = base_data()
    del segment(data, "s1")["slots"]["main"]["items"][1]["back_asset_key"]
    message = _errors(tmp_path, data)
    assert "flip" in message and "c2" in message


def test_move_requires_region(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s1")["beats"][1]["cues"][1]["to"] = "sidebar"
    assert "<槽位>@<區域>" in _errors(tmp_path, data)


@pytest.mark.parametrize("box", [[0.6, 0.0, 0.5, 0.5], [-0.1, 0.0, 0.5, 0.5], [0.0, 0.0, 0.0, 0.5]])
def test_region_out_of_range_rejected(tmp_path: Path, box: list[float]) -> None:
    data = base_data()
    data["assets"][3]["regions"]["zone_a"] = box
    message = _errors(tmp_path, data)
    assert "zone_a" in message and "0–1" in message


def test_unusable_asset_rejected(tmp_path: Path) -> None:
    data = base_data()
    data["assets"][1]["usable"] = False
    message = _errors(tmp_path, data)
    assert "red" in message and "不可用" in message


def test_source_pages_required(tmp_path: Path) -> None:
    data = base_data()
    del segment(data, "s2")["source_pages"]
    message = _errors(tmp_path, data)
    assert "s2" in message and "source_pages" in message

    # title_card 沒有旁白，不需要出處頁碼
    data = base_data()
    data["segments"].insert(0, {"segment_key": "t0", "chapter_key": "c1", "template": "title_card"})
    _load(tmp_path, data)


@pytest.mark.parametrize(
    "mutate, name",
    [
        (lambda d: segment(d, "s2").__setitem__("template", "side_by_side"), "side_by_side"),
        (
            lambda d: segment(d, "s2")["slots"].__setitem__("main", {"kind": "player_ring"}),
            "player_ring",
        ),
        (
            lambda d: d["assets"].append(
                {"asset_key": "die", "kind": "drawn", "priority": "optional", "reason": "x"}
            ),
            "drawn",
        ),
        (
            lambda d: segment(d, "s1")["beats"][0]["cues"].append(
                {"at": 0, "do": "fly", "target": "main"}
            ),
            "fly",
        ),
    ],
    ids=["template", "player_ring", "drawn", "action"],
)
def test_unsupported_rejected(tmp_path: Path, mutate, name: str) -> None:
    data = base_data()
    mutate(data)
    message = _errors(tmp_path, data)
    assert "本版尚未支援" in message and name in message


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: segment(d, "s2").__setitem__("start_sec", 12.0),
        lambda d: segment(d, "s2")["beats"][0].__setitem__("start_sec", 12.0),
        lambda d: segment(d, "s1")["beats"][0]["cues"][0].__setitem__("at", -0.5),
    ],
    ids=["segment-start_sec", "beat-start_sec", "negative-at"],
)
def test_absolute_time_rejected(tmp_path: Path, mutate) -> None:
    data = base_data()
    mutate(data)
    assert "自動計算" in _errors(tmp_path, data)


def test_missing_asset_file_rejected(tmp_path: Path) -> None:
    write_game(tmp_path, base_data())
    (tmp_path / "assets" / "blue.png").unlink()
    with pytest.raises(VideoDataError) as exc:
        load_video(tmp_path)
    assert "blue.png" in str(exc.value)
