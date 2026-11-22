"""店員拍規則書：切塊讀取、合併、圖說、照片品質（2026-11-22 永傑決定，看圖實驗第一～四輪的做法）。

單元測試：看圖模型用 FakeVisionProvider，不連資料庫、不需要金鑰。
"""

import io

import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.domains.rules_qa.video_rulebook import (
    CAPTION_SCHEMA,
    TILE_SCHEMA,
    merge_tiles,
    photo_quality,
    read_rulebook,
    sharpness,
    tile_boxes,
)
from app.integrations.ocr.errors import OCRUnavailable
from app.integrations.ocr.fake import FakeVisionProvider


def page_image(blur: float = 0) -> bytes:
    """自行畫的假規則書頁：深色底、很多白色細線（像小字）。"""
    image = Image.new("RGB", (600, 800), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    for y in range(40, 760, 18):
        for x in range(40, 560, 14):
            draw.rectangle((x, y, x + 8, y + 9), outline=(235, 235, 235))
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=90)
    return out.getvalue()


def tile(title: str, text: str) -> dict:
    return {"title": title, "text": text}


def caption(*descriptions: str) -> dict:
    return {
        "figures": [
            {"label": f"圖例{chr(65 + i)}", "kind": "example", "description": d}
            for i, d in enumerate(descriptions)
        ]
    }


# --- 切塊 ---


def test_four_tiles_with_six_percent_overlap():
    boxes = tile_boxes(1000, 2000)
    assert [name for name, _ in boxes] == ["左上", "右上", "左下", "右下"]
    left_top = dict(boxes)["左上"]
    right_bottom = dict(boxes)["右下"]
    assert left_top == (0, 0, 560, 1120)  # 一半再多 6%
    assert right_bottom == (440, 880, 1000, 2000)


# --- 合併 ---


def test_merge_drops_lines_cut_at_tile_edges_and_keeps_the_complete_one():
    # 左右切開的同一行：左邊那塊讀到前半、右邊那塊從重疊處讀到後半，接成一行
    # 上下切開的同一行：上下兩塊都讀到，留一行
    parts = {
        "左上": tile("開店準備", "1.把收銀機放在櫃台左邊。\n2.每位店員領取1件圍裙"),
        "右上": tile("", "1件圍裙、1頂帽子。"),
        "左下": tile("", "2.每位店員領取1件圍\n3.把1盒零錢放在櫃台右邊。"),
        "右下": tile("", "第二項"),
    }
    text = merge_tiles(parts)
    lines = text.split("\n")
    assert lines[0] == "開店準備"
    assert "2.每位店員領取1件圍裙、1頂帽子。" in lines
    assert sum("每位店員領取1件圍" in line for line in lines) == 1
    assert "3.把1盒零錢放在櫃台右邊。" in lines and "第二項" in lines


def test_merge_keeps_similar_but_different_lines():
    # 「3.右邊隨機…」和「4.左邊隨機…」只差兩個字，是不同的兩項
    parts = {
        "左上": tile("", "3.右邊的人先點1杯紅茶\n4.左邊的人先點1杯紅茶"),
        "右上": tile("", ""),
        "左下": tile("", "4.左邊的人先點1杯紅茶"),
        "右下": tile("", ""),
    }
    text = merge_tiles(parts)
    assert "3.右邊的人先點1杯紅茶" in text and text.count("4.左邊的人先點1杯紅茶") == 1


# --- 照片品質（清晰度，不用 LLM） ---


def test_sharp_photo_is_ok_and_blurry_photo_is_bad():
    sharp = sharpness(page_image())
    blurry = sharpness(page_image(blur=6))
    assert sharp > blurry
    assert photo_quality(sharp)[0] == "ok"
    level, message = photo_quality(blurry)
    assert level == "bad" and "重拍" in message


def test_quality_thresholds():
    assert photo_quality(1000) == ("ok", None)
    assert photo_quality(300)[0] == "warn"
    assert photo_quality(100)[0] == "bad"


# --- 讀取 ---


def _replies_for(*pages: tuple[list[dict], dict]) -> list:
    replies = []
    for tiles, cap in pages:
        replies += tiles + [cap]
    return replies


def test_read_rulebook_reads_tiles_then_captions():
    first = [
        tile("開店準備", "1.把收銀機放在櫃台左邊。"),
        tile("", "2.每位店員領取1件圍裙。"),
        tile("", "3.把1盒零錢放在櫃台右邊。"),
        tile("", ""),
    ]
    second = [tile("附圖丙", "出現客人"), tile("", ""), tile("", "走到等候區"), tile("", "")]
    vision = FakeVisionProvider(
        _replies_for((first, caption()), (second, caption("紅衣客人走到紅色區")))
    )
    progress: list[tuple[int, int]] = []
    pages = read_rulebook(
        vision, [page_image(), page_image()], workers=1, report=lambda d, t: progress.append((d, t))
    )
    # 每張：四塊各一次＋圖說一次
    assert [c.schema_name for c in vision.calls] == [TILE_SCHEMA.name] * 4 + [
        CAPTION_SCHEMA.name
    ] + [TILE_SCHEMA.name] * 4 + [CAPTION_SCHEMA.name]
    # 圖說要看整張照片，並附上切塊讀出的文字
    assert len(vision.calls[4].images) == 1
    assert "3.把1盒零錢放在櫃台右邊。" in vision.calls[4].input
    assert pages[0].text.startswith("開店準備\n1.把收銀機放在櫃台左邊。")
    assert "【圖說】" not in pages[0].text  # 沒有圖就不加圖說
    assert "【圖說】" in pages[1].text and "圖例A：紅衣客人走到紅色區" in pages[1].text
    assert pages[1].captions == ["圖例A：紅衣客人走到紅色區"]
    assert progress[-1] == (2, 2)


def test_tiles_are_cropped_from_the_photo():
    vision = FakeVisionProvider(_replies_for(([tile("", "x")] * 4, caption())))
    read_rulebook(vision, [page_image()], workers=1)
    # 每一塊都是 JPEG，而且比整張小
    whole = len(page_image())
    assert all(mime == "image/jpeg" for c in vision.calls[:4] for mime, _ in c.images)
    assert all(size < whole for c in vision.calls[:4] for _, size in c.images)


def test_usage_is_recorded_from_worker_threads():
    # 同時讀兩張（執行緒）時，每次看圖呼叫的用量仍記在同一份紀錄
    from app.integrations.llm.usage import collect_usage

    generic = {"title": "", "text": "x", "figures": []}
    vision = FakeVisionProvider([generic] * 10)
    with collect_usage() as usage:
        read_rulebook(vision, [page_image(), page_image()], workers=2)
    assert usage.summary()["calls"] == 10


def test_vision_unavailable_is_raised():
    vision = FakeVisionProvider([OCRUnavailable("連不上")])
    with pytest.raises(OCRUnavailable):
        read_rulebook(vision, [page_image()], workers=1)
