"""測試用的 HEIC 照片：用 pillow-heif 直接編碼（不註冊 Pillow 外掛，避免蓋過受測程式的設定）。"""

import io
import os

import pillow_heif
from PIL import Image

_EXIF_ORIENTATION = 0x0112


def heic_bytes(
    size: tuple[int, int] = (40, 20),
    *,
    mode: str = "RGB",
    exif_orientation: int | None = None,
    quality: int = 90,
) -> bytes:
    """一張純色的 HEIC；`exif_orientation` 給了就在 EXIF 寫方向標記（6＝要順時針轉 90 度）。"""
    color = (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)
    return encode_heic(Image.new(mode, size, color), exif_orientation, quality)


def noisy_heic_bytes(size: tuple[int, int], quality: int) -> bytes:
    """雜訊圖的 HEIC：幾乎壓不下來，用來做接近上限的大檔（4032×3024、品質 80 約 15 MB）。"""
    width, height = size
    return encode_heic(Image.frombytes("RGB", size, os.urandom(width * height * 3)), None, quality)


def encode_heic(image: Image.Image, exif_orientation: int | None, quality: int) -> bytes:
    kwargs = {}
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[_EXIF_ORIENTATION] = exif_orientation
        kwargs["exif"] = exif.tobytes()
    out = io.BytesIO()
    pillow_heif.from_pillow(image).save(out, quality=quality, **kwargs)
    data = out.getvalue()
    assert data[4:12] == b"ftypheic", data[:16]
    return data


def mpo_bytes(size: tuple[int, int] = (40, 20), *, exif_orientation: int | None = None) -> bytes:
    """多圖 JPEG（MPO）：主圖加一張小的附圖，像 iPhone 轉出來附 HDR 增益圖的 JPEG。"""
    main = Image.new("RGB", size, (200, 30, 30))
    extra = Image.new("RGB", (size[0] // 2, size[1] // 2), (0, 0, 0))
    kwargs = {}
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[_EXIF_ORIENTATION] = exif_orientation
        kwargs["exif"] = exif
    out = io.BytesIO()
    main.save(out, "MPO", save_all=True, append_images=[extra], **kwargs)
    data = out.getvalue()
    assert Image.open(io.BytesIO(data)).format == "MPO"
    return data


def broken_heic_bytes() -> bytes:
    """檔頭是 HEIC、內容被截斷的壞檔。"""
    data = heic_bytes((64, 48))
    return data[: len(data) // 2]
