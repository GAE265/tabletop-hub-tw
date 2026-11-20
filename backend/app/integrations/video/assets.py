"""讀取素材圖片：依 orientation 擺正、依 crop 裁切，並快取縮放後的結果。"""

from functools import lru_cache

from PIL import Image

from app.integrations.video.model import Region, Video


class AssetLibrary:
    def __init__(self, video: Video) -> None:
        self.video = video
        self._images: dict[tuple[str, Region | None], Image.Image] = {}

    def image(self, asset_key: str, crop: Region | None = None) -> Image.Image:
        """擺正（並裁切）後的 RGBA 圖片。"""
        cache_key = (asset_key, crop)
        if cache_key not in self._images:
            asset = self.video.assets[asset_key]
            with Image.open(self.video.asset_path(asset_key)) as raw:
                image = raw.convert("RGBA")
            if asset.orientation:
                # orientation 是照片需要順時針轉幾度才會擺正
                image = image.rotate(-asset.orientation, expand=True)
            if crop is not None:
                w, h = image.size
                image = image.crop(
                    (
                        round(crop.x * w),
                        round(crop.y * h),
                        round((crop.x + crop.w) * w),
                        round((crop.y + crop.h) * h),
                    )
                )
            self._images[cache_key] = image
        return self._images[cache_key]

    def size(self, asset_key: str, crop: Region | None = None) -> tuple[int, int]:
        return self.image(asset_key, crop).size

    def resized(
        self, asset_key: str, width: int, height: int, crop: Region | None = None
    ) -> Image.Image:
        return _resize(self, asset_key, max(1, width), max(1, height), crop)


@lru_cache(maxsize=512)
def _resize(
    library: AssetLibrary, asset_key: str, width: int, height: int, crop: Region | None
) -> Image.Image:
    return library.image(asset_key, crop).resize((width, height), Image.Resampling.LANCZOS)
