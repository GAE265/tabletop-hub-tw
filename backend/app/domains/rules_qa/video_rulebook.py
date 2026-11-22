"""店員拍規則書：照片品質、切塊讀取、合併、圖說（2026-11-22 永傑決定；看圖實驗第一～四輪）。

- 每張照片切成 2×2 四塊、相鄰重疊 6%，各讀一次（整張讀時 Azure 會把圖縮小，小字容易讀錯；
  切塊後關鍵詞正確率約從 85% 提高到 95%，編造的字也幾乎消失）。
- 四塊的文字依「左上、右上、左下、右下」合併；一行包含另一行（切在邊上只讀到半行）時視為重複，
  留完整的那一行；只差幾個字的行不算重複（例如「3.右邊…」「4.左邊…」）。
- 圖說：整張照片＋合併後的文字一起給看圖模型（圖需要整體脈絡），名稱以照片為準，
  正文有寫、圖上沒畫的不寫。
- 照片品質只看清晰度（拉普拉斯變異數，不用 LLM）：低於 150 請重拍，150～500 提示可能讀錯。
"""

import io
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from app.integrations.llm.types import JsonSchema
from app.integrations.ocr.base import VisionProvider
from app.integrations.storage import FileNotFound, FileStorage

TILE_OVERLAP = 0.06
TILE_ORDER = ("左上", "右上", "左下", "右下")

# 清晰度門檻（看圖實驗第三輪：原圖與 LINE 壓縮版的正常照片都在 598 以上；
# 低於 150 時三張測試頁的正確率都掉 20 個百分點以上）
SHARPNESS_BAD = 150
SHARPNESS_WARN = 500
BLURRY_MESSAGE = "照片太模糊，請重拍"
MAYBE_BLURRY_MESSAGE = "照片可能不夠清楚，建議重拍"

TILE_INSTRUCTIONS = """你會看到一頁桌遊規則書手機照片的其中一塊
（照片切成四塊分開讀，邊緣的字可能被切到）。
請只寫這一塊上看得到的文字，不可以補上照片上沒有的內容。
- title：這一塊裡這一頁的大標題（沒有就給空字串）。
- text：這一塊上印的所有文字（標題、正文、表格、圖上的標示文字），依閱讀順序一字不改地照抄，
  每一行一行。表格每一列寫成一行，欄位用「｜」隔開。看不清楚的字用「□」代替，不要猜。
  被切到只剩一半的字或行，照看得到的部分寫。"""

TILE_SCHEMA = JsonSchema(
    name="rulebook_tile",
    schema={
        "type": "object",
        "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
        "required": ["title", "text"],
        "additionalProperties": False,
    },
)

CAPTION_INSTRUCTIONS = """你會看到一張桌遊規則書的手機照片，
以及從這張照片切成小塊讀出的文字（可能有少數錯字）。
請描述這一頁的每一張圖（圖例、範例圖、配置圖；表格不算圖）。沒有圖就給空陣列。
- 圖上的名稱、標示文字以照片為準；照片上看不清楚時，可以參考讀出的文字，
  但只能用讀出的文字裡有的詞。
- 只寫圖上看得到的東西：圖例寫出每個圖示或區域對應的名稱；
  範例寫出圖上畫出的每一步（哪張牌移到哪裡）；
  配置圖寫出每個區域的相對位置。正文有寫、但圖上沒有畫出來的，不要寫進圖說。
- label 是圖上或旁邊印的代號（例如「圖例A」），沒有就給 null。"""

CAPTION_SCHEMA = JsonSchema(
    name="rulebook_captions",
    schema={
        "type": "object",
        "properties": {
            "figures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": ["string", "null"]},
                        "kind": {
                            "type": "string",
                            "enum": ["legend", "example", "layout", "other"],
                        },
                        "description": {"type": "string"},
                    },
                    "required": ["label", "kind", "description"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["figures"],
        "additionalProperties": False,
    },
)

CAPTION_HEADING = "【圖說】"


@dataclass(frozen=True)
class ReadPage:
    """讀出的一頁：合併後的文字（有圖時後面接【圖說】）與圖說。"""

    text: str
    captions: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- 品質


def sharpness(data: bytes) -> float:
    """拉普拉斯變異數：灰階、縮成寬 1000 像素後計算（不同解析度可以比較）。"""
    import numpy as np

    gray = Image.open(io.BytesIO(data)).convert("L")
    if gray.width != 1000:
        gray = gray.resize((1000, max(1, round(gray.height * 1000 / gray.width))))
    a = np.asarray(gray, dtype=float)
    lap = a[1:-1, :-2] + a[1:-1, 2:] + a[:-2, 1:-1] + a[2:, 1:-1] - 4 * a[1:-1, 1:-1]
    return round(float(lap.var()), 1)


def photo_quality(score: float) -> tuple[str, str | None]:
    """（ok｜warn｜bad, 給店員的說明）。"""
    if score < SHARPNESS_BAD:
        return "bad", BLURRY_MESSAGE
    if score < SHARPNESS_WARN:
        return "warn", MAYBE_BLURRY_MESSAGE
    return "ok", None


# --------------------------------------------------------------------------- 切塊與合併


def tile_boxes(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """2×2 四塊，相鄰重疊 TILE_OVERLAP（左上、右上、左下、右下）。"""
    o = TILE_OVERLAP
    rel = {
        "左上": (0, 0, 0.5 + o, 0.5 + o),
        "右上": (0.5 - o, 0, 1, 0.5 + o),
        "左下": (0, 0.5 - o, 0.5 + o, 1),
        "右下": (0.5 - o, 0.5 - o, 1, 1),
    }
    return [
        (name, (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)))
        for name, (x0, y0, x1, y1) in rel.items()
    ]


def _squash(value: str) -> str:
    return "".join(value.split())


MIN_OVERLAP = 4  # 判斷「同一行」至少要重疊幾個字
LEFT_OF = {"右上": "左上", "右下": "左下"}


def _after(line: str, count: int) -> str:
    """line 去掉前 count 個非空白字之後剩下的部分。"""
    seen = 0
    for i, char in enumerate(line):
        if seen == count:
            return line[i:]
        if not char.isspace():
            seen += 1
    return ""


def merge_tiles(parts: dict[str, dict[str, Any]]) -> str:
    """依左上、右上、左下、右下逐行加入，去掉重疊區重複讀到的文字：

    - 一行包含前面別塊的某一行（或被它包含）：上下切開時兩塊都讀到，留完整的那一行。
    - 右邊那塊的一行，開頭和左邊那塊某一行的結尾重疊 4 字以上：左右切開的同一行，接成一行。
    只差幾個字的行不算重複（例如「3.右邊…」「4.左邊…」是不同的兩項）。
    """
    kept: list[str] = []
    keys: list[str] = []  # 和 kept 對應的比對用文字（去空白）
    owner: list[str] = []  # 每一行來自哪一塊
    for name in TILE_ORDER:
        part = parts.get(name) or {}
        for line in [part.get("title") or ""] + (part.get("text") or "").split("\n"):
            key = _squash(line)
            if len(key) < 2:
                continue
            others = [i for i in range(len(kept)) if owner[i] != name]
            hit = next((i for i in others if key in keys[i] or keys[i] in key), None)
            if hit is not None and min(len(key), len(keys[hit])) >= MIN_OVERLAP:
                if len(key) > len(keys[hit]):
                    kept[hit], keys[hit] = line.strip(), key
                continue
            joined = False
            for i in (i for i in others if owner[i] == LEFT_OF.get(name)):
                for size in range(min(len(key), len(keys[i])) - 1, MIN_OVERLAP - 1, -1):
                    if keys[i].endswith(key[:size]):
                        kept[i] = kept[i].rstrip() + _after(line.strip(), size)
                        keys[i] = keys[i] + key[size:]
                        joined = True
                        break
                if joined:
                    break
            if joined:
                continue
            kept.append(line.strip())
            keys.append(key)
            owner.append(name)
    return "\n".join(kept)


def _jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


# --------------------------------------------------------------------------- 讀取


def _read_one(vision: VisionProvider, data: bytes, parallel: bool) -> ReadPage:
    image = Image.open(io.BytesIO(data))
    crops = [(name, _jpeg(image.crop(box))) for name, box in tile_boxes(*image.size)]

    def read_tile(item: tuple[str, bytes]) -> tuple[str, dict[str, Any]]:
        name, crop = item
        prompt = f"這是一頁規則書照片的「{name}」部分。請讀這一塊。"
        return name, vision.generate_json(
            instructions=TILE_INSTRUCTIONS, input=prompt, images=[crop], schema=TILE_SCHEMA
        )

    if parallel:
        with ThreadPoolExecutor(max_workers=len(crops)) as pool:
            parts = dict(pool.map(read_tile, crops))
    else:
        parts = dict(map(read_tile, crops))
    merged = merge_tiles(parts)
    result = vision.generate_json(
        instructions=CAPTION_INSTRUCTIONS,
        input=f"切塊讀出的文字：\n{merged}",
        images=[data],
        schema=CAPTION_SCHEMA,
    )
    captions = [
        f"{f['label']}：{f['description']}" if f.get("label") else f["description"]
        for f in result.get("figures", [])
        if (f.get("description") or "").strip()
    ]
    text = merged
    if captions:
        text += f"\n\n{CAPTION_HEADING}\n" + "\n".join(captions)
    return ReadPage(text=text, captions=captions)


def read_rulebook(
    vision: VisionProvider,
    photos: list[bytes],
    workers: int = 3,
    report: Callable[[int, int], None] | None = None,
) -> list[ReadPage]:
    """依順序讀每一張照片（每張：四塊、合併、圖說）。workers＝同時讀幾張；1＝全部依序（測試用）。

    看圖模型的錯誤（OCRUnavailable 等）直接往外拋。
    """
    done = 0
    lock = threading.Lock()

    def one(data: bytes) -> ReadPage:
        nonlocal done
        page = _read_one(vision, data, parallel=workers > 1)
        with lock:
            done += 1
            if report is not None:
                report(done, len(photos))
        return page

    if workers <= 1:
        return [one(data) for data in photos]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, photos))


# --------------------------------------------------------------------------- 照片清單（存放介面）
# 照片與清單都放在存放介面 rules_videos/<專案>/rulebook/；不用 migration。
# 清單：{"photos": [{"file", "width", "height", "sharpness"}]}，順序就是頁的順序。

MAX_RULEBOOK_PHOTOS = 40


def rulebook_photo_key(project_id: object, file: str) -> str:
    return f"rules_videos/{project_id}/rulebook/{file}"


def manifest_key(project_id: object) -> str:
    return f"rules_videos/{project_id}/rulebook/manifest.json"


def load_manifest(storage: FileStorage, project_id: object) -> list[dict[str, Any]]:
    """還沒有清單時是空的；存放介面其他錯誤往外拋。"""
    import json

    try:
        data = storage.get(manifest_key(project_id))
    except FileNotFound:
        return []
    return list(json.loads(data.decode("utf-8")).get("photos", []))


def save_manifest(storage: FileStorage, project_id: object, photos: list[dict[str, Any]]) -> None:
    import json

    body = json.dumps({"photos": photos}, ensure_ascii=False).encode("utf-8")
    storage.put(manifest_key(project_id), body, "application/json")


def read_photo_files(page_texts: dict[str, Any]) -> list[str]:
    """頁面文字是從哪些照片讀出來的（依頁的順序）；不是照片讀出的頁不列。"""
    pages = sorted((int(k), v) for k, v in page_texts.items() if isinstance(v, dict))
    return [v["photo"] for _, v in pages if v.get("photo")]


def is_read(page_texts: dict[str, Any], photos: list[dict[str, Any]]) -> bool:
    """照片都讀過了：頁面文字正好是依這些照片、這個順序讀出來的。"""
    return bool(photos) and read_photo_files(page_texts) == [p["file"] for p in photos]
