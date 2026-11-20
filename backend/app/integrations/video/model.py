"""段資料格式（spec rules-video-maker「段資料格式與驗證」）。

一個 `video.json` 描述一支影片：章、專案層的素材清單、依序排列的段。
載入時一次檢查所有錯誤，訊息指出哪一段、哪一句、哪個欄位；格式錯誤就不渲染。
段資料不存絕對秒數，時間由 timeline.py 依旁白與動作長度計算。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.integrations.video.errors import VideoDataError
from app.integrations.video.templates import (
    DEFAULT_TEMPLATE,
    RESERVED_SLOT_KINDS,
    SLOT_KINDS,
    TEMPLATES,
)

FORMAT_VERSION = 1
DEFAULT_VOICE = "zh-TW-YunJheNeural"
ACTIONS = ("show", "hide", "flip", "shuffle", "move")
ASSET_KINDS = ("flat_photo", "drawn")
# 已保留名稱、本版尚未支援的素材種類
RESERVED_ASSET_KINDS = ("drawn",)
PRIORITIES = ("must", "optional")
ORIENTATIONS = (0, 90, 180, 270)
SHAPES = ("box", "cross")
HIGHLIGHT_STYLES = ("gold", "red")
LABEL_STYLES = ("plain", "gold", "red")
LABEL_POSITIONS = ("below", "above", "center")
ANIMS = ("pop", "fade")
TRANSITIONS = ("cut", "fade")
# 這些欄位代表絕對時間；出現就報錯，提醒時間是自動計算的
ABSOLUTE_TIME_FIELDS = ("start_sec", "end_sec", "slot_sec", "time_sec", "duration_sec")


@dataclass(frozen=True)
class Region:
    """素材上的具名區域，0–1 的相對比例。"""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Asset:
    asset_key: str
    kind: str  # flat_photo | drawn
    priority: str  # must（必拍）| optional（選拍）
    reason: str  # 觀眾必須從這個素材讀到什麼資訊
    file: str | None = None
    shot: str | None = None
    regions: dict[str, Region] = field(default_factory=dict)
    orientation: int = 0
    usable: bool | None = None  # None：還沒確認
    quality: dict[str, Any] | None = None  # 預留給第 4 階段


@dataclass(frozen=True)
class Item:
    item_key: str
    asset_key: str
    back_asset_key: str | None = None
    hidden: bool = False


@dataclass(frozen=True)
class Slot:
    kind: str  # asset | items | text | bullets
    hidden: bool = False
    asset_key: str | None = None
    crop: Region | None = None
    items: tuple[Item, ...] = ()
    text: str | None = None
    title: str | None = None
    bullets: tuple[str, ...] = ()
    emphasis: tuple[str, ...] = ()


@dataclass(frozen=True)
class Highlight:
    key: str
    target: str
    shape: str = "box"
    style: str = "gold"


@dataclass(frozen=True)
class Label:
    key: str
    text: str
    target: str
    position: str = "below"
    style: str = "plain"


@dataclass(frozen=True)
class Cue:
    at: float  # 從該句開始算的秒數
    do: str
    target: str
    to: str | None = None
    anim: str = "pop"
    duration: float | None = None


@dataclass(frozen=True)
class Beat:
    beat_key: str
    narration: str
    subtitle: str
    keywords: tuple[str, ...] = ()
    cues: tuple[Cue, ...] = ()


@dataclass(frozen=True)
class Timing:
    min_beat_sec: float = 2.6
    pad_before: float = 0.15
    pad_after: float = 0.4
    cue_hold: float = 0.3


@dataclass(frozen=True)
class SourcePage:
    lang: str
    page: int


@dataclass(frozen=True)
class Segment:
    segment_key: str
    chapter_key: str
    template: str = DEFAULT_TEMPLATE
    slots: dict[str, Slot] = field(default_factory=dict)
    highlights: tuple[Highlight, ...] = ()
    labels: tuple[Label, ...] = ()
    beats: tuple[Beat, ...] = ()
    timing: Timing = Timing()
    transition_in: str = "cut"
    source_pages: tuple[SourcePage, ...] = ()
    # 預留：獨立狀態與修改紀錄（第 2 階段使用），本階段原樣保留
    state: dict[str, Any] = field(default_factory=dict)
    revisions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Chapter:
    chapter_key: str
    number: int
    title: str


@dataclass(frozen=True)
class Video:
    format_version: int
    game_key: str
    title: str
    voice: str
    chapters: tuple[Chapter, ...]
    assets: dict[str, Asset]
    segments: tuple[Segment, ...]
    base_dir: Path

    def asset_path(self, asset_key: str) -> Path:
        asset = self.assets[asset_key]
        return self.base_dir / "assets" / (asset.file or "")

    def chapter(self, chapter_key: str) -> Chapter:
        return next(c for c in self.chapters if c.chapter_key == chapter_key)


# --------------------------------------------------------------------------- 解析


class _Parser:
    """把 JSON 轉成資料物件，同時收集錯誤；一次回報全部錯誤。"""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}：{message}" if where else message)

    def obj(self, value: Any, where: str) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.error(where, "必須是物件")
            return None
        return value

    def fields(self, data: dict[str, Any], where: str, allowed: tuple[str, ...]) -> None:
        for name in data:
            if name in ABSOLUTE_TIME_FIELDS:
                self.error(where, f"不能寫 {name}：時間由旁白與動作長度自動計算")
            elif name not in allowed:
                self.error(where, f"未知的欄位 {name}")

    def text(self, data: dict[str, Any], name: str, where: str, *, required: bool = True) -> str:
        value = data.get(name)
        if value is None:
            if required:
                self.error(where, f"缺少 {name}")
            return ""
        if not isinstance(value, str) or (required and not value.strip()):
            self.error(where, f"{name} 必須是非空字串")
            return ""
        return value

    def optional_text(self, data: dict[str, Any], name: str, where: str) -> str | None:
        if data.get(name) is None:
            return None
        return self.text(data, name, where)

    def choice(
        self, data: dict[str, Any], name: str, where: str, choices: tuple[str, ...], default: str
    ) -> str:
        value = data.get(name, default)
        if value not in choices:
            self.error(where, f"{name} 必須是 {'、'.join(choices)} 之一，收到 {value!r}")
            return default
        return value

    def number(self, data: dict[str, Any], name: str, where: str, default: float) -> float:
        value = data.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int | float):
            self.error(where, f"{name} 必須是數字")
            return default
        return float(value)

    def strings(self, data: dict[str, Any], name: str, where: str) -> tuple[str, ...]:
        value = data.get(name, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            self.error(where, f"{name} 必須是字串陣列")
            return ()
        return tuple(value)

    def items(self, data: dict[str, Any], name: str, where: str) -> list[Any]:
        value = data.get(name, [])
        if not isinstance(value, list):
            self.error(where, f"{name} 必須是陣列")
            return []
        return value

    def box(self, value: Any, where: str, name: str) -> Region | None:
        if (
            not isinstance(value, list)
            or len(value) != 4
            or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)
        ):
            self.error(where, f"{name} 必須是 [x, y, w, h] 四個數字")
            return None
        x, y, w, h = (float(v) for v in value)
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 + 1e-9 or y + h > 1 + 1e-9:
            self.error(where, f"{name} 超出 0–1 的範圍：{value}")
            return None
        return Region(x, y, w, h)


def load_video(folder: Path | str) -> Video:
    """載入資料夾內的 video.json 並驗證；有任何錯誤就拋 VideoDataError。"""
    folder = Path(folder)
    path = folder / "video.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VideoDataError([f"找不到段資料檔：{path}"]) from exc
    except json.JSONDecodeError as exc:
        raise VideoDataError([f"video.json 不是合法的 JSON：{exc}"]) from exc
    return parse_video(raw, folder)


def parse_video(raw: Any, base_dir: Path) -> Video:
    p = _Parser()
    data = p.obj(raw, "video.json") or {}
    p.fields(
        data,
        "video.json",
        ("format_version", "game_key", "title", "voice", "chapters", "assets", "segments"),
    )
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        p.error("video.json", f"不認得的 format_version：{version!r}（本版為 {FORMAT_VERSION}）")
    # 頂層欄位要在下面的「有錯就拋出」之前解析，錯誤才會一起回報
    game_key = p.text(data, "game_key", "video.json")
    title = p.text(data, "title", "video.json")
    voice = p.optional_text(data, "voice", "video.json") or DEFAULT_VOICE

    chapters = _parse_chapters(p, data)
    assets = _parse_assets(p, data, base_dir)
    segments = [
        _parse_segment(p, raw_seg, i)
        for i, raw_seg in enumerate(p.items(data, "segments", "video.json"))
    ]
    segments = [s for s in segments if s is not None]
    if not segments:
        p.error("video.json", "至少要有一段")

    _check_unique(p, "段", [s.segment_key for s in segments])
    _check_unique(p, "句", [b.beat_key for s in segments for b in s.beats])
    chapter_keys = {c.chapter_key for c in chapters}
    for seg in segments:
        _validate_segment(p, seg, assets, chapter_keys)

    if p.errors:
        raise VideoDataError(p.errors)
    return Video(
        format_version=FORMAT_VERSION,
        game_key=game_key,
        title=title,
        voice=voice,
        chapters=tuple(chapters),
        assets=assets,
        segments=tuple(segments),
        base_dir=base_dir,
    )


def _check_unique(p: _Parser, what: str, keys: list[str], where: str = "") -> None:
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            p.error(where, f"{what}的 key 重複：{key}")
        seen.add(key)


def _parse_chapters(p: _Parser, data: dict[str, Any]) -> list[Chapter]:
    chapters = []
    for i, raw in enumerate(p.items(data, "chapters", "video.json")):
        where = f"chapters[{i}]"
        item = p.obj(raw, where)
        if item is None:
            continue
        p.fields(item, where, ("chapter_key", "number", "title"))
        number = item.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            p.error(where, "number 必須是整數")
            number = 0
        chapters.append(
            Chapter(
                chapter_key=p.text(item, "chapter_key", where),
                number=number,
                title=p.text(item, "title", where),
            )
        )
    if not chapters:
        p.error("video.json", "至少要有一章（chapters）")
    _check_unique(p, "章", [c.chapter_key for c in chapters])
    return chapters


def _parse_assets(p: _Parser, data: dict[str, Any], base_dir: Path) -> dict[str, Asset]:
    assets: dict[str, Asset] = {}
    keys: list[str] = []
    for i, raw in enumerate(p.items(data, "assets", "video.json")):
        item = p.obj(raw, f"assets[{i}]")
        if item is None:
            continue
        key = p.text(item, "asset_key", f"assets[{i}]")
        where = f"素材 {key or i}"
        p.fields(
            item,
            where,
            (
                "asset_key",
                "kind",
                "priority",
                "reason",
                "shot",
                "file",
                "drawn",
                "regions",
                "orientation",
                "usable",
                "quality",
            ),
        )
        kind = item.get("kind")
        if kind in RESERVED_ASSET_KINDS:
            p.error(where, f"本版尚未支援的素材種類：{kind}")
        elif kind not in ASSET_KINDS:
            p.error(where, f"kind 必須是 {'、'.join(ASSET_KINDS)} 之一，收到 {kind!r}")
        orientation = item.get("orientation", 0)
        if orientation not in ORIENTATIONS:
            p.error(where, f"orientation 必須是 0、90、180、270 之一，收到 {orientation!r}")
            orientation = 0
        usable = item.get("usable")
        if usable not in (None, True, False):
            p.error(where, "usable 必須是 null、true 或 false")
            usable = None
        regions: dict[str, Region] = {}
        raw_regions = item.get("regions", {})
        if not isinstance(raw_regions, dict):
            p.error(where, "regions 必須是物件")
        else:
            for name, box in raw_regions.items():
                region = p.box(box, where, f"區域 {name}")
                if region is not None:
                    regions[name] = region
        file = p.optional_text(item, "file", where)
        if kind == "flat_photo":
            if file is None:
                p.error(where, "flat_photo 素材必須有 file")
            elif not (base_dir / "assets" / file).is_file():
                p.error(where, f"素材檔案不存在：assets/{file}")
        keys.append(key)
        assets[key] = Asset(
            asset_key=key,
            kind=kind if isinstance(kind, str) else "",
            priority=p.choice(item, "priority", where, PRIORITIES, "must"),
            reason=p.text(item, "reason", where),
            file=file,
            shot=p.optional_text(item, "shot", where),
            regions=regions,
            orientation=orientation,
            usable=usable,
            quality=item.get("quality"),
        )
    _check_unique(p, "素材", keys)
    return assets


def _parse_slot(p: _Parser, raw: Any, where: str) -> Slot | None:
    item = p.obj(raw, where)
    if item is None:
        return None
    kind = item.get("kind")
    if kind in RESERVED_SLOT_KINDS:
        p.error(where, f"本版尚未支援的槽位內容：{kind}")
        return None
    if kind not in SLOT_KINDS:
        p.error(where, f"本版尚未支援的槽位內容：{kind!r}")
        return None
    hidden = bool(item.get("hidden", False))
    if kind == "asset":
        p.fields(item, where, ("kind", "hidden", "asset_key", "crop"))
        crop = p.box(item["crop"], where, "crop") if "crop" in item else None
        return Slot(kind, hidden, asset_key=p.text(item, "asset_key", where), crop=crop)
    if kind == "items":
        p.fields(item, where, ("kind", "hidden", "items"))
        parsed = []
        for i, raw_item in enumerate(p.items(item, "items", where)):
            entry = p.obj(raw_item, f"{where} 第 {i + 1} 項")
            if entry is None:
                continue
            item_where = f"{where} 項 {entry.get('item_key', i + 1)}"
            p.fields(entry, item_where, ("item_key", "asset_key", "back_asset_key", "hidden"))
            parsed.append(
                Item(
                    item_key=p.text(entry, "item_key", item_where),
                    asset_key=p.text(entry, "asset_key", item_where),
                    back_asset_key=p.optional_text(entry, "back_asset_key", item_where),
                    hidden=bool(entry.get("hidden", False)),
                )
            )
        if not parsed:
            p.error(where, "items 至少要有一項")
        return Slot(kind, hidden, items=tuple(parsed))
    if kind == "text":
        p.fields(item, where, ("kind", "hidden", "text", "title", "emphasis"))
        return Slot(
            kind,
            hidden,
            text=p.text(item, "text", where),
            title=p.optional_text(item, "title", where),
            emphasis=p.strings(item, "emphasis", where),
        )
    p.fields(item, where, ("kind", "hidden", "items", "title", "emphasis"))
    bullets = p.strings(item, "items", where)
    if not bullets:
        p.error(where, "bullets 至少要有一項")
    return Slot(
        kind,
        hidden,
        bullets=bullets,
        title=p.optional_text(item, "title", where),
        emphasis=p.strings(item, "emphasis", where),
    )


def _parse_cue(p: _Parser, raw: Any, where: str) -> Cue | None:
    item = p.obj(raw, where)
    if item is None:
        return None
    p.fields(item, where, ("at", "do", "target", "to", "anim", "duration"))
    at = p.number(item, "at", where, 0.0)
    if at < 0:
        p.error(where, "at 不能小於 0：時間由旁白與動作長度自動計算，at 是從這一句開始算的秒數")
    do = item.get("do")
    if do not in ACTIONS:
        p.error(where, f"本版尚未支援的動作：{do!r}（只有 {'、'.join(ACTIONS)}）")
        return None
    duration = item.get("duration")
    if duration is not None:
        duration = p.number(item, "duration", where, 1.0)
        if duration <= 0:
            p.error(where, "duration 必須大於 0")
    return Cue(
        at=at,
        do=do,
        target=p.text(item, "target", where),
        to=p.optional_text(item, "to", where),
        anim=p.choice(item, "anim", where, ANIMS, "pop"),
        duration=duration,
    )


def _parse_segment(p: _Parser, raw: Any, index: int) -> Segment | None:
    data = p.obj(raw, f"segments[{index}]")
    if data is None:
        return None
    key = p.text(data, "segment_key", f"segments[{index}]")
    where = f"段 {key or index}"
    p.fields(
        data,
        where,
        (
            "segment_key",
            "chapter_key",
            "template",
            "slots",
            "highlights",
            "labels",
            "beats",
            "timing",
            "transition_in",
            "source_pages",
            "state",
            "revisions",
        ),
    )
    template = data.get("template", DEFAULT_TEMPLATE)
    if template not in TEMPLATES:
        p.error(where, f"本版尚未支援的版型：{template!r}")

    slots: dict[str, Slot] = {}
    raw_slots = data.get("slots", {})
    if not isinstance(raw_slots, dict):
        p.error(where, "slots 必須是物件")
        raw_slots = {}
    for name, raw_slot in raw_slots.items():
        slot = _parse_slot(p, raw_slot, f"{where} 槽位 {name}")
        if slot is not None:
            slots[name] = slot

    highlights = []
    for i, raw_h in enumerate(p.items(data, "highlights", where)):
        h = p.obj(raw_h, f"{where} highlights[{i}]")
        if h is None:
            continue
        h_where = f"{where} highlight {h.get('key', i)}"
        p.fields(h, h_where, ("key", "target", "shape", "style"))
        highlights.append(
            Highlight(
                key=p.text(h, "key", h_where),
                target=p.text(h, "target", h_where),
                shape=p.choice(h, "shape", h_where, SHAPES, "box"),
                style=p.choice(h, "style", h_where, HIGHLIGHT_STYLES, "gold"),
            )
        )

    labels = []
    for i, raw_l in enumerate(p.items(data, "labels", where)):
        lab = p.obj(raw_l, f"{where} labels[{i}]")
        if lab is None:
            continue
        l_where = f"{where} label {lab.get('key', i)}"
        p.fields(lab, l_where, ("key", "text", "target", "position", "style"))
        labels.append(
            Label(
                key=p.text(lab, "key", l_where),
                text=p.text(lab, "text", l_where),
                target=p.text(lab, "target", l_where),
                position=p.choice(lab, "position", l_where, LABEL_POSITIONS, "below"),
                style=p.choice(lab, "style", l_where, LABEL_STYLES, "plain"),
            )
        )

    beats = []
    for i, raw_b in enumerate(p.items(data, "beats", where)):
        b = p.obj(raw_b, f"{where} beats[{i}]")
        if b is None:
            continue
        b_where = f"{where} 句 {b.get('beat_key', i + 1)}"
        p.fields(b, b_where, ("beat_key", "narration", "subtitle", "keywords", "cues"))
        cues = [
            _parse_cue(p, raw_c, f"{b_where} cue {j + 1}")
            for j, raw_c in enumerate(p.items(b, "cues", b_where))
        ]
        beats.append(
            Beat(
                beat_key=p.text(b, "beat_key", b_where),
                narration=p.text(b, "narration", b_where),
                subtitle=p.text(b, "subtitle", b_where),
                keywords=p.strings(b, "keywords", b_where),
                cues=tuple(c for c in cues if c is not None),
            )
        )

    timing = Timing()
    raw_timing = data.get("timing")
    if raw_timing is not None:
        t = p.obj(raw_timing, f"{where} timing") or {}
        p.fields(t, f"{where} timing", ("min_beat_sec", "pad_before", "pad_after", "cue_hold"))
        timing = Timing(
            min_beat_sec=p.number(t, "min_beat_sec", where, timing.min_beat_sec),
            pad_before=p.number(t, "pad_before", where, timing.pad_before),
            pad_after=p.number(t, "pad_after", where, timing.pad_after),
            cue_hold=p.number(t, "cue_hold", where, timing.cue_hold),
        )

    pages = []
    for i, raw_page in enumerate(p.items(data, "source_pages", where)):
        page = p.obj(raw_page, f"{where} source_pages[{i}]")
        if page is None:
            continue
        p.fields(page, f"{where} source_pages[{i}]", ("lang", "page"))
        number = page.get("page")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            p.error(where, "source_pages 的 page 必須是正整數")
            continue
        pages.append(SourcePage(lang=p.text(page, "lang", where), page=number))

    state = data.get("state", {})
    if not isinstance(state, dict):
        p.error(where, "state 必須是物件")
        state = {}
    revisions = data.get("revisions", [])
    if not isinstance(revisions, list):
        p.error(where, "revisions 必須是陣列")
        revisions = []

    return Segment(
        segment_key=key,
        chapter_key=p.text(data, "chapter_key", where),
        template=template if template in TEMPLATES else DEFAULT_TEMPLATE,
        slots=slots,
        highlights=tuple(highlights),
        labels=tuple(labels),
        beats=tuple(beats),
        timing=timing,
        transition_in=p.choice(data, "transition_in", where, TRANSITIONS, "cut"),
        source_pages=tuple(pages),
        state=state,
        revisions=tuple(revisions),
    )


# --------------------------------------------------------------------------- 語意檢查


@dataclass(frozen=True)
class Target:
    """cue、highlight、label 指向的對象。"""

    kind: str  # slot | item | region | highlight | label
    slot: str | None = None
    name: str | None = None  # item_key、區域名稱、highlight／label 的 key


def resolve_target(segment: Segment, assets: dict[str, Asset], text: str) -> Target | None:
    """把 `main`、`main.c2`、`sidebar@zone`、highlight／label 的 key 轉成 Target；找不到回 None。"""
    if "@" in text:
        slot_name, _, region = text.partition("@")
        slot = segment.slots.get(slot_name)
        if slot is None or slot.kind != "asset" or slot.asset_key not in assets:
            return None
        if region not in assets[slot.asset_key].regions:
            return None
        return Target("region", slot_name, region)
    if "." in text:
        slot_name, _, item_key = text.partition(".")
        slot = segment.slots.get(slot_name)
        if slot is None or slot.kind != "items":
            return None
        if not any(item.item_key == item_key for item in slot.items):
            return None
        return Target("item", slot_name, item_key)
    if text in segment.slots:
        return Target("slot", text)
    if any(h.key == text for h in segment.highlights):
        return Target("highlight", name=text)
    if any(lab.key == text for lab in segment.labels):
        return Target("label", name=text)
    return None


def find_item(segment: Segment, slot: str, item_key: str) -> Item:
    return next(i for i in segment.slots[slot].items if i.item_key == item_key)


def _validate_segment(
    p: _Parser, seg: Segment, assets: dict[str, Asset], chapter_keys: set[str]
) -> None:
    where = f"段 {seg.segment_key}"
    spec = TEMPLATES[seg.template]
    if seg.chapter_key and seg.chapter_key not in chapter_keys:
        p.error(where, f"chapter_key {seg.chapter_key} 不在 chapters 中")

    # 槽位
    for name, slot in seg.slots.items():
        slot_spec = spec.slots.get(name)
        if slot_spec is None:
            available = "、".join(spec.slots) or "（這個版型沒有槽位）"
            p.error(where, f"版型 {seg.template} 沒有槽位 {name}；可用的槽位：{available}")
            continue
        if slot.kind not in slot_spec.kinds:
            p.error(
                where,
                f"槽位 {name} 不能放 {slot.kind}；可放的種類：{'、'.join(slot_spec.kinds)}",
            )
    for name, slot_spec in spec.slots.items():
        if slot_spec.required and name not in seg.slots:
            p.error(where, f"缺少必填槽位 {name}")

    # 素材引用
    def check_asset(asset_key: str | None, slot_where: str) -> None:
        if not asset_key:
            return
        asset = assets.get(asset_key)
        if asset is None:
            p.error(slot_where, f"找不到素材 {asset_key}")
        elif asset.usable is False:
            p.error(slot_where, f"素材 {asset_key} 已標記為不可用（usable=false）")

    item_keys: list[str] = []
    for name, slot in seg.slots.items():
        slot_where = f"{where} 槽位 {name}"
        check_asset(slot.asset_key, slot_where)
        for item in slot.items:
            check_asset(item.asset_key, f"{slot_where} 項 {item.item_key}")
            check_asset(item.back_asset_key, f"{slot_where} 項 {item.item_key}")
            item_keys.append(item.item_key)
    _check_unique(p, "項", item_keys, where)
    overlay_keys = [h.key for h in seg.highlights] + [lab.key for lab in seg.labels]
    _check_unique(p, "highlight／label", overlay_keys, where)
    for key in overlay_keys:
        if key in seg.slots:
            p.error(where, f"highlight／label 的 key 重複：{key} 與槽位名稱相同")

    # 旁白與出處
    if spec.has_beats:
        if not seg.beats:
            p.error(where, "至少要有一句（beats）")
        elif not seg.source_pages:
            p.error(where, "有旁白的段必須有 source_pages：旁白只能依據規則書，請標示頁碼")
    elif seg.beats:
        p.error(where, f"版型 {seg.template} 沒有旁白，不能有 beats")

    # highlight 與 label 的對象
    for h in seg.highlights:
        target = resolve_target(seg, assets, h.target)
        if target is None or target.kind not in ("slot", "item", "region"):
            p.error(f"{where} highlight {h.key}", f"找不到 target {h.target}")
    for lab in seg.labels:
        target = resolve_target(seg, assets, lab.target)
        if target is None or target.kind not in ("slot", "item", "region"):
            p.error(f"{where} label {lab.key}", f"找不到 target {lab.target}")

    # cue
    for beat in seg.beats:
        for n, cue in enumerate(beat.cues, start=1):
            _validate_cue(p, seg, assets, cue, f"{where} 句 {beat.beat_key} cue {n}")


_ALLOWED_TARGETS = {
    "show": ("slot", "item", "highlight", "label"),
    "hide": ("item", "highlight", "label"),
    "flip": ("slot", "item"),
    "shuffle": ("slot",),
    "move": ("item",),
}


def _validate_cue(p: _Parser, seg: Segment, assets: dict[str, Asset], cue: Cue, where: str) -> None:
    target = resolve_target(seg, assets, cue.target)
    if target is None:
        p.error(where, f"找不到 target {cue.target}")
        return
    if target.kind not in _ALLOWED_TARGETS[cue.do]:
        p.error(where, f"{cue.do} 不能用在 {cue.target}")
        return
    if cue.do in ("flip", "shuffle") and target.kind == "slot":
        if seg.slots[cue.target].kind != "items":
            p.error(where, f"{cue.do} 只能用在 items 槽位或其中一項")
            return
    if cue.do == "flip":
        items = (
            seg.slots[target.slot or cue.target].items
            if target.kind == "slot"
            else (find_item(seg, target.slot or "", target.name or ""),)
        )
        for item in items:
            if item.back_asset_key is None:
                p.error(where, f"flip 的項 {item.item_key} 沒有 back_asset_key（沒有背面可以翻）")
    if cue.do == "move":
        if not cue.to or "@" not in cue.to:
            p.error(where, f"move 的目的地必須是 <槽位>@<區域>，收到 {cue.to!r}")
            return
        destination = resolve_target(seg, assets, cue.to)
        if destination is None or destination.kind != "region":
            p.error(where, f"找不到 move 的目的地 {cue.to}")
    elif cue.to is not None:
        p.error(where, "只有 move 可以寫 to")
