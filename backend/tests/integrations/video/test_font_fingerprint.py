"""字型的快取鍵要隨字型檔內容改變（tasks 4.15，#75 審核延後的項目）。"""

from pathlib import Path

from app.integrations.video.fonts import FontSet, font_fingerprint


def test_fingerprint_changes_when_file_content_changes(tmp_path: Path) -> None:
    path = tmp_path / "font.ttc"
    path.write_bytes(b"first font file")
    first = font_fingerprint(str(path))
    path.write_bytes(b"second font file, same path")
    assert font_fingerprint(str(path)) != first


def test_fingerprint_same_content_same_key(tmp_path: Path) -> None:
    a, b = tmp_path / "a.ttc", tmp_path / "b.ttc"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    assert font_fingerprint(str(a)) == font_fingerprint(str(b))


def test_fallback_cache_key_unchanged() -> None:
    assert FontSet(None, None).cache_key == "pillow-default"
