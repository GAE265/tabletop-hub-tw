"""檔案儲存整合層（spec：openspec/changes/add-rules-video-maker/specs/media-integrations）。

fake 與 local 照同一份介面行為測試；雲端實作只在 test_file_storage_external.py 測。
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.integrations.storage import (
    FakeFileStorage,
    FileNotFound,
    FileStorage,
    LocalFileStorage,
    StorageConfig,
    get_file_storage,
)


@pytest.fixture(params=["fake", "local"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[FileStorage]:
    if request.param == "fake":
        yield FakeFileStorage()
    else:
        yield LocalFileStorage(root=tmp_path, public_base_url="http://api.test/media")


def test_put_then_get_returns_same_bytes(storage: FileStorage) -> None:
    url = storage.put("videos/p1/final.mp4", b"\x00\x01mp4", "video/mp4")
    assert url
    assert storage.get("videos/p1/final.mp4") == b"\x00\x01mp4"


def test_put_same_key_replaces_content(storage: FileStorage) -> None:
    storage.put("photos/p1/1.jpg", b"old", "image/jpeg")
    storage.put("photos/p1/1.jpg", b"new", "image/jpeg")
    assert storage.get("photos/p1/1.jpg") == b"new"


def test_delete_then_get_raises_file_not_found(storage: FileStorage) -> None:
    storage.put("photos/p1/1.jpg", b"jpg", "image/jpeg")
    storage.delete("photos/p1/1.jpg")
    with pytest.raises(FileNotFound):
        storage.get("photos/p1/1.jpg")


def test_get_missing_raises_file_not_found(storage: FileStorage) -> None:
    with pytest.raises(FileNotFound):
        storage.get("nothing/here.mp4")


def test_delete_missing_does_not_raise(storage: FileStorage) -> None:
    storage.delete("nothing/here.mp4")
    storage.delete("nothing/here.mp4")


@pytest.mark.parametrize(
    "key",
    ["", "/abs.mp4", "../escape.mp4", "a/../../escape.mp4", "a\\b.mp4", "a//b.mp4", "空白 .mp4"],
)
def test_unsafe_key_is_rejected(storage: FileStorage, key: str) -> None:
    """key 只能是相對路徑（英數、-、_、.、/），不能跳出儲存位置。"""
    with pytest.raises(ValueError):
        storage.put(key, b"x", "video/mp4")


def test_local_url_is_public_base_url_plus_key(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path, public_base_url="http://api.test/media/")
    url = storage.put("videos/p1/final.mp4", b"mp4", "video/mp4")
    assert url == "http://api.test/media/videos/p1/final.mp4"
    assert (tmp_path / "videos" / "p1" / "final.mp4").read_bytes() == b"mp4"


def test_fake_records_content_type() -> None:
    storage = FakeFileStorage()
    storage.put("videos/p1/final.mp4", b"mp4", "video/mp4")
    assert storage.content_types["videos/p1/final.mp4"] == "video/mp4"


def test_factory_fake_and_local(tmp_path: Path) -> None:
    assert isinstance(get_file_storage(StorageConfig(provider="fake")), FakeFileStorage)
    local = get_file_storage(
        StorageConfig(
            provider="local", local_dir=str(tmp_path), public_base_url="http://api.test/media"
        )
    )
    assert isinstance(local, LocalFileStorage)


def test_factory_local_missing_settings_names_them() -> None:
    with pytest.raises(ValueError, match="local_dir.*public_base_url"):
        get_file_storage(StorageConfig(provider="local"))


def test_factory_cloud_missing_settings_names_them() -> None:
    with pytest.raises(ValueError, match="connection_string.*container"):
        get_file_storage(StorageConfig(provider="cloud"))


def test_factory_unknown_provider() -> None:
    with pytest.raises(ValueError, match="未知的檔案儲存 provider"):
        get_file_storage(StorageConfig(provider="s3"))
