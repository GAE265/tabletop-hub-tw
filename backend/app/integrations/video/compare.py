"""逐項比對兩份段資料（spec rules-video-script「逐項比對」）。

a 是要檢查的版本（例如 AI 草稿），b 是參考版本（例如手寫版）：
只有 b 有的叫「缺少」，只有 a 有的叫「多出」。報告只列差異，不判定合格與否。
句內動作會把 target 換算成素材（例如 `main.c2` → 藍牌），所以兩邊的項目命名不同也能對齊。
"""

import difflib
from dataclasses import dataclass, field

from app.integrations.video.model import Cue, Segment, Slot, Video, resolve_target

CATEGORIES = (
    "分段",
    "旁白與字幕",
    "素材",
    "槽位",
    "句內動作",
    "highlight 與 label",
    "區域",
    "出處頁碼",
)
SAME, DIFFERENT, MISSING, EXTRA = "相同", "不同", "缺少", "多出"


@dataclass
class Counts:
    same: int = 0
    different: int = 0
    missing: int = 0
    extra: int = 0

    def add(self, status: str) -> None:
        if status == SAME:
            self.same += 1
        elif status == DIFFERENT:
            self.different += 1
        elif status == MISSING:
            self.missing += 1
        else:
            self.extra += 1


@dataclass(frozen=True)
class Item:
    """一個比對項目：名稱、狀態、兩邊的內容。"""

    name: str
    status: str
    a: str | None
    b: str | None


@dataclass(frozen=True)
class BeatPair:
    index: int
    status: str
    a_key: str | None
    b_key: str | None
    a_narration: str | None
    b_narration: str | None
    a_subtitle: str | None
    b_subtitle: str | None
    narration_similarity: float
    subtitle_similarity: float


@dataclass(frozen=True)
class CueDiff:
    beat_index: int
    status: str
    a: str | None
    b: str | None
    at_delta: float | None  # a 的 at 減 b 的 at（秒）；只有對上的動作才有


@dataclass
class CompareReport:
    a_label: str
    b_label: str
    summary: dict[str, Counts] = field(default_factory=lambda: {c: Counts() for c in CATEGORIES})
    segment_counts: tuple[tuple[int, list[int]], tuple[int, list[int]]] = ((0, []), (0, []))
    segments: list[Item] = field(default_factory=list)
    beats: list[BeatPair] = field(default_factory=list)
    assets: list[Item] = field(default_factory=list)
    slots: list[Item] = field(default_factory=list)
    cues: list[CueDiff] = field(default_factory=list)
    overlays: list[Item] = field(default_factory=list)
    regions: list[Item] = field(default_factory=list)
    pages: list[Item] = field(default_factory=list)

    def markdown(self) -> str:
        return _markdown(self)


def compare_videos(
    a: Video, b: Video, a_label: str = "AI 草稿", b_label: str = "手寫"
) -> CompareReport:
    report = CompareReport(a_label, b_label)
    _compare_segments(report, a, b)
    _compare_beats(report, a, b)
    _compare_assets(report, a, b)
    _compare_slots(report, a, b)
    _compare_cues(report, a, b)
    _compare_overlays(report, a, b)
    _compare_regions(report, a, b)
    _compare_pages(report, a, b)
    return report


# --------------------------------------------------------------------------- 各項比對


def _pairs(a: list, b: list) -> list[tuple[int, object | None, object | None]]:
    """依順序配對；比較短的一邊用 None 補齊。"""
    return [
        (i, a[i] if i < len(a) else None, b[i] if i < len(b) else None)
        for i in range(max(len(a), len(b)))
    ]


def _status(a: object | None, b: object | None) -> str:
    if a is None:
        return MISSING
    if b is None:
        return EXTRA
    return SAME if a == b else DIFFERENT


def _record(report: CompareReport, category: str, items: list[Item], item: Item) -> None:
    items.append(item)
    report.summary[category].add(item.status)


def _compare_segments(report: CompareReport, a: Video, b: Video) -> None:
    a_counts = [len(s.beats) for s in a.segments]
    b_counts = [len(s.beats) for s in b.segments]
    report.segment_counts = ((len(a.segments), a_counts), (len(b.segments), b_counts))
    for i, x, y in _pairs(a_counts, b_counts):
        item = Item(
            f"第 {i + 1} 段的句數",
            _status(x, y),
            None if x is None else f"{x} 句",
            None if y is None else f"{y} 句",
        )
        _record(report, "分段", report.segments, item)


def _flat_beats(video: Video) -> list:
    return [beat for segment in video.segments for beat in segment.beats]


def _similarity(x: str | None, y: str | None) -> float:
    if x is None or y is None:
        return 0.0
    return difflib.SequenceMatcher(None, x, y).ratio()


def _compare_beats(report: CompareReport, a: Video, b: Video) -> None:
    for i, x, y in _pairs(_flat_beats(a), _flat_beats(b)):
        if x is None or y is None:
            status = MISSING if x is None else EXTRA
        elif x.narration == y.narration and x.subtitle == y.subtitle:
            status = SAME
        else:
            status = DIFFERENT
        pair = BeatPair(
            index=i,
            status=status,
            a_key=getattr(x, "beat_key", None),
            b_key=getattr(y, "beat_key", None),
            a_narration=getattr(x, "narration", None),
            b_narration=getattr(y, "narration", None),
            a_subtitle=getattr(x, "subtitle", None),
            b_subtitle=getattr(y, "subtitle", None),
            narration_similarity=_similarity(
                getattr(x, "narration", None), getattr(y, "narration", None)
            ),
            subtitle_similarity=_similarity(
                getattr(x, "subtitle", None), getattr(y, "subtitle", None)
            ),
        )
        report.beats.append(pair)
        report.summary["旁白與字幕"].add(status)


def _asset_text(video: Video, key: str) -> str:
    asset = video.assets[key]
    priority = "必拍" if asset.priority == "must" else "選拍"
    return f"{asset.kind}、{priority}：{asset.reason}"


def _compare_assets(report: CompareReport, a: Video, b: Video) -> None:
    for key in sorted(set(a.assets) | set(b.assets)):
        x, y = a.assets.get(key), b.assets.get(key)
        if x is None or y is None:
            status = _status(x, y)
        else:
            status = SAME if (x.kind, x.priority) == (y.kind, y.priority) else DIFFERENT
        item = Item(
            key,
            status,
            None if x is None else _asset_text(a, key),
            None if y is None else _asset_text(b, key),
        )
        _record(report, "素材", report.assets, item)


def _slot_text(slot: Slot) -> str:
    if slot.kind == "asset":
        return f"素材 {slot.asset_key}"
    if slot.kind == "items":
        return "一排：" + "、".join(item.asset_key for item in slot.items)
    if slot.kind == "text":
        return f"文字：{slot.text}"
    return "條列：" + "／".join(slot.bullets)


def _compare_slots(report: CompareReport, a: Video, b: Video) -> None:
    for i, x, y in _pairs(list(a.segments), list(b.segments)):
        x_slots = {} if x is None else {n: _slot_text(s) for n, s in x.slots.items()}
        y_slots = {} if y is None else {n: _slot_text(s) for n, s in y.slots.items()}
        for name in sorted(set(x_slots) | set(y_slots)):
            p, q = x_slots.get(name), y_slots.get(name)
            item = Item(f"第 {i + 1} 段 {name}", _status(p, q), p, q)
            _record(report, "槽位", report.slots, item)


def _target_text(video: Video, segment: Segment, text: str) -> str:
    """把 target 換算成不受命名影響的描述：項目換成它的素材。"""
    target = resolve_target(segment, video.assets, text)
    if target is None:
        return text
    if target.kind == "item":
        item = next(i for i in segment.slots[target.slot or ""].items if i.item_key == target.name)
        return f"{target.slot}[{item.asset_key}]"
    if target.kind == "highlight":
        h = next(h for h in segment.highlights if h.key == target.name)
        return f"框選（{_target_text(video, segment, h.target)}，{h.shape}、{h.style}）"
    if target.kind == "label":
        label = next(lab for lab in segment.labels if lab.key == target.name)
        return f"標籤「{label.text}」"
    return text


def _cue_text(video: Video, segment: Segment, cue: Cue) -> str:
    text = f"{cue.do} {_target_text(video, segment, cue.target)}"
    if cue.to:
        text += f" → {_target_text(video, segment, cue.to)}"
    return text


def _flat_cues(video: Video) -> list[list[tuple[str, float]]]:
    """每一句的動作序列：（描述, at）。"""
    return [
        [(_cue_text(video, segment, cue), cue.at) for cue in beat.cues]
        for segment in video.segments
        for beat in segment.beats
    ]


def _compare_cues(report: CompareReport, a: Video, b: Video) -> None:
    counts = report.summary["句內動作"]
    for i, x, y in _pairs(_flat_cues(a), _flat_cues(b)):
        x, y = x or [], y or []
        matcher = difflib.SequenceMatcher(None, [c[0] for c in x], [c[0] for c in y])
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for p, q in zip(x[i1:i2], y[j1:j2], strict=True):
                    diff = CueDiff(i, SAME, p[0], q[0], round(p[1] - q[1], 3))
                    report.cues.append(diff)
                    counts.add(SAME)
                continue
            left, right = x[i1:i2], y[j1:j2]
            for k in range(max(len(left), len(right))):
                p = left[k] if k < len(left) else None
                q = right[k] if k < len(right) else None
                status = _status(p, q) if p is None or q is None else DIFFERENT
                diff = CueDiff(i, status, p and p[0], q and q[0], None)
                report.cues.append(diff)
                counts.add(status)


def _overlay_texts(video: Video, segment: Segment) -> set[str]:
    texts = {
        f"框選（{_target_text(video, segment, h.target)}，{h.shape}、{h.style}）"
        for h in segment.highlights
    }
    for lab in segment.labels:
        target = _target_text(video, segment, lab.target)
        texts.add(f"標籤「{lab.text}」（{target}，{lab.position}、{lab.style}）")
    return texts


def _compare_overlays(report: CompareReport, a: Video, b: Video) -> None:
    for i, x, y in _pairs(list(a.segments), list(b.segments)):
        x_set = set() if x is None else _overlay_texts(a, x)
        y_set = set() if y is None else _overlay_texts(b, y)
        for text in sorted(x_set | y_set):
            p = text if text in x_set else None
            q = text if text in y_set else None
            _record(
                report,
                "highlight 與 label",
                report.overlays,
                Item(f"第 {i + 1} 段", _status(p, q), p, q),
            )


def _region_names(video: Video) -> set[str]:
    return {f"{key}@{name}" for key, asset in video.assets.items() for name in asset.regions}


def _compare_regions(report: CompareReport, a: Video, b: Video) -> None:
    x_set, y_set = _region_names(a), _region_names(b)
    for name in sorted(x_set | y_set):
        p = name if name in x_set else None
        q = name if name in y_set else None
        _record(report, "區域", report.regions, Item(name, _status(p, q), p, q))


def _pages_text(segment: Segment) -> str:
    return "、".join(f"{p.lang} 第 {p.page} 頁" for p in segment.source_pages) or "（無）"


def _compare_pages(report: CompareReport, a: Video, b: Video) -> None:
    for i, x, y in _pairs(list(a.segments), list(b.segments)):
        p = None if x is None else _pages_text(x)
        q = None if y is None else _pages_text(y)
        _record(report, "出處頁碼", report.pages, Item(f"第 {i + 1} 段", _status(p, q), p, q))


# --------------------------------------------------------------------------- 報告


def _cell(text: str | None) -> str:
    if text is None:
        return "—"
    return text.replace("|", "\\|").replace("\n", " ")


def _item_table(items: list[Item], a_label: str, b_label: str) -> list[str]:
    lines = [f"| 項目 | 狀態 | {a_label} | {b_label} |", "|---|---|---|---|"]
    lines += [f"| {_cell(i.name)} | {i.status} | {_cell(i.a)} | {_cell(i.b)} |" for i in items]
    return lines


def _markdown(report: CompareReport) -> str:
    a, b = report.a_label, report.b_label
    (a_segments, a_counts), (b_segments, b_counts) = report.segment_counts
    lines = [
        "# 段資料逐項比對",
        "",
        f"- 比對：**{a}**（左）與 **{b}**（右）",
        f"- 「缺少」＝只有{b}有；「多出」＝只有{a}有。報告不判定合格與否。",
        "",
        "## 摘要",
        "",
        "| 項目 | 相同 | 不同 | 缺少 | 多出 |",
        "|---|---|---|---|---|",
    ]
    for category in CATEGORIES:
        c = report.summary[category]
        lines.append(f"| {category} | {c.same} | {c.different} | {c.missing} | {c.extra} |")

    lines += [
        "",
        "## 分段",
        "",
        f"- {a}：{a_segments} 段，每段句數 {a_counts}",
        f"- {b}：{b_segments} 段，每段句數 {b_counts}",
        "",
        "## 旁白與字幕（依句的順序）",
        "",
        f"| # | 狀態 | 相似度 | {a} | {b} |",
        "|---|---|---|---|---|",
    ]
    for pair in report.beats:
        lines.append(
            f"| {pair.index + 1} 旁白 | {pair.status} | {pair.narration_similarity:.2f} "
            f"| {_cell(pair.a_narration)} | {_cell(pair.b_narration)} |"
        )
        lines.append(
            f"| {pair.index + 1} 字幕 |  | {pair.subtitle_similarity:.2f} "
            f"| {_cell(pair.a_subtitle)} | {_cell(pair.b_subtitle)} |"
        )

    sections = (
        ("素材清單", report.assets),
        ("槽位", report.slots),
        ("highlight 與 label", report.overlays),
        ("區域", report.regions),
        ("出處頁碼", report.pages),
    )
    for title, items in sections[:2]:
        lines += ["", f"## {title}", "", *_item_table(items, a, b)]

    lines += [
        "",
        "## 句內動作（依句的順序；項目換算成素材）",
        "",
        f"| 句 | 狀態 | {a} | {b} | at 相差（秒） |",
        "|---|---|---|---|---|",
    ]
    for diff in report.cues:
        delta = "" if diff.at_delta is None else f"{diff.at_delta:+.2f}"
        cells = (str(diff.beat_index + 1), diff.status, _cell(diff.a), _cell(diff.b), delta)
        lines.append("| " + " | ".join(cells) + " |")

    for title, items in sections[2:]:
        lines += ["", f"## {title}", "", *_item_table(items, a, b)]
    return "\n".join(lines) + "\n"
