"""VIDEO_MUSIC_VOLUME 的範圍（tasks 4.18，#75 審核延後的項目）。"""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("volume", [1.5, -0.1])
def test_music_volume_out_of_range(make_settings: Callable[..., Settings], volume: float) -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(video_music_volume=volume)
    assert "video_music_volume" in str(exc.value)


@pytest.mark.parametrize("volume", [0.0, 1.0, 0.25])
def test_music_volume_in_range(make_settings: Callable[..., Settings], volume: float) -> None:
    assert make_settings(video_music_volume=volume).video_music_volume == volume
