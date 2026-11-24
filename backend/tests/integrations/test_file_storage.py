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


# --- 刪除整個前綴（刪除影片專案時清掉 rules_videos/<專案>/ 底下的所有檔案） ---


def test_delete_prefix_removes_everything_under_it(storage: FileStorage) -> None:
    for key in ("rv/p1/assets/a.jpg", "rv/p1/renders/j1.mp4", "rv/p1/rulebook/manifest.json"):
        storage.put(key, b"x", "application/octet-stream")
    storage.put("rv/p2/assets/a.jpg", b"keep", "image/jpeg")
    assert storage.delete_prefix("rv/p1") == 3
    for key in ("rv/p1/assets/a.jpg", "rv/p1/renders/j1.mp4", "rv/p1/rulebook/manifest.json"):
        with pytest.raises(FileNotFound):
            storage.get(key)
    assert storage.get("rv/p2/assets/a.jpg") == b"keep"


def test_delete_prefix_only_matches_whole_folder(storage: FileStorage) -> None:
    # 「rv/abc」不可以刪到「rv/abcd/...」：前綴一律當成資料夾
    storage.put("rv/abc/x.jpg", b"x", "image/jpeg")
    storage.put("rv/abcd/x.jpg", b"keep", "image/jpeg")
    assert storage.delete_prefix("rv/abc/") == 1
    assert storage.get("rv/abcd/x.jpg") == b"keep"


def test_delete_prefix_missing_returns_zero(storage: FileStorage) -> None:
    assert storage.delete_prefix("rv/nothing") == 0
    assert storage.delete_prefix("rv/nothing") == 0


@pytest.mark.parametrize("prefix", ["", "/", "/abs", "..", "a/../b", "a\\b", "a//b"])
def test_unsafe_prefix_is_rejected(storage: FileStorage, prefix: str) -> None:
    storage.put("a/b.jpg", b"keep", "image/jpeg")
    with pytest.raises(ValueError):
        storage.delete_prefix(prefix)
    assert storage.get("a/b.jpg") == b"keep"


def test_local_delete_prefix_removes_folder(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path, public_base_url="http://api.test/media")
    storage.put("rv/p1/assets/a.jpg", b"x", "image/jpeg")
    storage.delete_prefix("rv/p1")
    assert not (tmp_path / "rv" / "p1").exists()
    assert (tmp_path / "rv").is_dir()


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
