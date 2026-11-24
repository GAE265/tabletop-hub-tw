"""規則教學與問答 API 的請求與回應格式（spec rules-qa）。"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.domains.rules_qa.video_script import TERMS_MAX, TermIn

# 問題去掉前後空白後 1–500 字
MESSAGE_MAX_CHARS = 500


class RulesLessonItem(BaseModel):
    game_id: int
    game_name: str
    has_video: bool
    has_rulebook: bool


class RulesLessonList(BaseModel):
    items: list[RulesLessonItem]
    total: int


class VideoOut(BaseModel):
    source: Literal["youtube", "file"]
    video_url: str
    youtube_id: str | None
    title: str


class RulesLessonOut(BaseModel):
    game_id: int
    game_name: str
    # 沒有教學影片時為 null
    video: VideoOut | None
    has_rulebook: bool
    suggested_questions: list[str]


class VideoRequest(BaseModel):
    # 只接受 YouTube 網址；格式由 service 解析，不合法回 RULES_QA_INVALID_VIDEO_URL
    video_url: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MessageRequest(BaseModel):
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_CHARS)
    ]
    # 上一則回答的 response_id；必填，新對話給 null。漏了這個欄位或給空字串回 422，
    # 避免前端漏送時默默忘記前面的對話（與推薦 Agent 相同）
    previous_response_id: Annotated[str, StringConstraints(min_length=1)] | None


class Citation(BaseModel):
    page: int


class MessageResponse(BaseModel):
    response_id: str
    answer: str
    # 規則書中找不到答案時為 false，此時 citations 為空
    answerable: bool
    citations: list[Citation]


# --------------------------------------------------------------------------- 規則影片專案

# 章節標題去掉前後空白後 1–50 字（add-rules-video-mobile design.md D1）
CHAPTER_TITLE_MAX_CHARS = 50
ChapterTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=CHAPTER_TITLE_MAX_CHARS)
]


class VideoProjectCreate(BaseModel):
    """建立專案。只給 game_id＝整個遊戲一支影片（店員的入口，建立後自動產生草稿）；
    chapter_number 與 chapter_title 一起給＝舊的單章模式（命令列與既有資料）。只給一個回 422。
    """

    game_id: int
    chapter_number: Annotated[int, Field(ge=1)] | None = None
    chapter_title: ChapterTitle | None = None
    # 店家人員不用填（用登入身分的店家，填別家店回 403）；管理員必填
    shop_id: uuid.UUID | None = None
    # 規則書來源：imported＝管理員匯入的（預設，建立後自動產生草稿）；
    # photos＝店員拍規則書（2026-11-22 永傑決定；只限整個遊戲，先拍照，再產生草稿）
    rulebook: Literal["imported", "photos"] = "imported"

    @model_validator(mode="after")
    def _both_or_neither(self) -> "VideoProjectCreate":
        if (self.chapter_number is None) != (self.chapter_title is None):
            raise ValueError(
                "chapter_number 與 chapter_title 要一起給（單章），或都不給（整個遊戲）"
            )
        if self.rulebook == "photos" and self.chapter_number is not None:
            raise ValueError("拍規則書只能用在整個遊戲一支影片")
        return self


class VideoProjectOut(BaseModel):
    id: uuid.UUID
    game_id: int
    game_name: str
    shop_id: uuid.UUID
    created_by: uuid.UUID
    # 舊的單章專案才有；整個遊戲一支影片時是 null
    chapter_number: int | None
    chapter_title: str | None
    # 影片標題：整個遊戲是「〈遊戲〉 規則教學」；單章是章節標題
    title: str
    # 目前步驟：不存欄位，由專案的狀態推出（design.md D1、D11）：
    # pages＝單章專案還沒有草稿（選頁、編輯文字）；draft＝整個遊戲在產生草稿，或有草稿、
    # 還沒拍照也沒略過；
    # assets＝素材還沒齊；render＝齊了、還沒有成品；done＝有成功產生的影片（D15）；
    # rulebook＝照片模式還沒讀規則書照片（店員拍規則書）
    step: Literal["rulebook", "pages", "draft", "assets", "render", "done"]
    # 規則書來源：imported＝管理員匯入的；photos＝店員拍的照片
    rulebook: Literal["imported", "photos"] = "imported"
    created_at: datetime
    updated_at: datetime


class RulebookPhotoOut(BaseModel):
    # 不隨刪除改變的代號（手機頁的縮圖快取用）
    id: str
    # 第幾張（從 1 開始），就是頁的順序
    index: int
    width: int
    height: int
    # 清晰度：ok｜warn（可能讀錯，建議重拍）｜bad（太模糊，請重拍）
    quality: Literal["ok", "warn", "bad"]
    quality_message: str | None = None


class RulebookOut(BaseModel):
    photos: list[RulebookPhotoOut]
    # 這些照片都讀過了（之後重新產生草稿不用再讀）
    read: bool


class VideoProjectList(BaseModel):
    items: list[VideoProjectOut]
    total: int


# --------------------------------------------------------------------------- 規則影片的非同步工作

JobKind = Literal["draft", "render", "revise"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class VideoJobOut(BaseModel):
    """工作的狀態。error 給店員看；給開發者看的 error_detail 不在 API 回傳。"""

    id: uuid.UUID
    project_id: uuid.UUID
    kind: JobKind
    status: JobStatus
    progress: float
    message: str | None
    error: str | None
    result: dict[str, Any] | None
    created_by: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class VideoJobList(BaseModel):
    items: list[VideoJobOut]
    total: int


# --------------------------------------------------------------------------- 規則影片的用語對照表


class VideoTermsIn(BaseModel):
    """上傳的對照表：整份取代。每筆的規則與命令列的 terms.json 共用（design.md D4）。"""

    terms: Annotated[list[TermIn], Field(max_length=TERMS_MAX)]


class VideoTermOut(BaseModel):
    en: str
    zh: str
    key: str | None
    avoid: list[str]
    category: Literal["generic", "single"] | None


class VideoTermsOut(BaseModel):
    game_id: int
    terms: list[VideoTermOut]
    updated_by: uuid.UUID
    updated_at: datetime


# --------------------------------------------------------------------------- 規則書頁面文字

PAGES_MAX = 20
PAGE_TEXT_MAX_CHARS = 10000
PageNumber = Annotated[int, Field(ge=1)]


class VideoPagesIn(BaseModel):
    """選頁與編輯後的文字（整份取代）；沒給文字的頁用原文（design.md D11）。"""

    chapter_pages: Annotated[list[PageNumber], Field(min_length=1, max_length=PAGES_MAX)]
    reference_pages: Annotated[list[PageNumber], Field(max_length=PAGES_MAX)] = []
    texts: dict[int, Annotated[str, Field(max_length=PAGE_TEXT_MAX_CHARS)]] = {}

    @model_validator(mode="after")
    def _check_pages(self) -> "VideoPagesIn":
        if len(set(self.chapter_pages)) != len(self.chapter_pages):
            raise ValueError("本章頁不能重複")
        if len(set(self.reference_pages)) != len(self.reference_pages):
            raise ValueError("參考頁不能重複")
        overlap = sorted(set(self.chapter_pages) & set(self.reference_pages))
        if overlap:
            raise ValueError(f"本章頁與參考頁不能重疊：{overlap}")
        extra = sorted(set(self.texts) - set(self.chapter_pages) - set(self.reference_pages))
        if extra:
            raise ValueError(f"texts 只能有選了的頁：{extra}")
        return self


class RemovedBlockOut(BaseModel):
    lines: list[str]


class ChangedLineOut(BaseModel):
    original: str
    edited: str
    similarity: float


class VideoPageOut(BaseModel):
    page: int
    role: Literal["chapter", "reference"]
    # games_manual 目前的原文；那一頁被刪掉時為 null
    original: str | None
    text: str
    # 開始編輯後，原文被重新上傳過（或被刪掉）
    original_changed: bool
    removed: list[RemovedBlockOut]
    changed: list[ChangedLineOut]


class VideoPagesOut(BaseModel):
    available_pages: list[int]
    chapter_pages: list[int]
    reference_pages: list[int]
    pages_version: int
    pages: list[VideoPageOut]


# --------------------------------------------------------------------------- 草稿


class VideoJobCreate(BaseModel):
    """建立工作：draft＝產生草稿（MR 5）、render＝產生影片（MR 9）；revise 在之後的 MR 加上。"""

    kind: Literal["draft", "render"]


class DraftBeatOut(BaseModel):
    beat_key: str
    narration: str
    subtitle: str


class DraftItemOut(BaseModel):
    """放牌的格子裡的一張牌。"""

    item_key: str
    asset_key: str
    # 沒有牌背時是 null
    back_asset_key: str | None = None


class DraftSlotOut(BaseModel):
    """一段裡放素材的格子（換素材，2026-11-25）。文字、條列的格子不列。"""

    # 格子名稱：main（主畫面）、sidebar（側欄）
    slot: str
    # asset＝單一素材；items＝放好幾張牌（正面與牌背都列在 asset_keys）
    kind: Literal["asset", "items"]
    # 這一格用到的素材（依出現順序、不重複）
    asset_keys: list[str]
    # 可以換素材（完整版：單一素材的格子、放牌的格子都可以）
    swappable: bool
    # 放牌的格子的每一張牌；單一素材的格子是空的
    items: list[DraftItemOut] = []


class DraftSegmentOut(BaseModel):
    segment_key: str
    # 屬於哪一格（setup／round／win）；單章專案是 c<章節編號>
    chapter: str
    source_pages: list[int]
    beats: list[DraftBeatOut]
    # 放素材的格子（換素材，2026-11-25）
    slots: list[DraftSlotOut] = []


class DraftAssetOut(BaseModel):
    asset_key: str
    # 給店員看的中文名稱；舊的草稿沒有時是 null
    label: str | None = None
    kind: str
    priority: str
    reason: str
    shot: str | None
    # 泛稱的素材：reason 寫了「代表牌」，店員可以換成同類的任一張牌
    representative: bool
    regions: list[str]
    # 已經標好座標的區域（重新產生草稿前提示「已標的區域會要重標」）
    marked_regions: list[str] = []
    has_photo: bool
    # 店員略過的素材（MR 9）
    skipped: bool = False
    # 可以略過：略過後每一段仍有主要內容（程式判斷，不看 priority）
    skippable: bool = False
    # 用到這個素材的段號（從 1 開始）；空的代表沒有段在用，不用拍（換素材，2026-11-25）
    used_in_segments: list[int] = []


class CoverageIssueOut(BaseModel):
    rule_id: str
    category: str
    source: str
    narration_status: str
    narration_missing: str | None
    subtitle_status: str
    subtitle_missing: str | None
    narration_shorter: bool


class CoverageProblemOut(BaseModel):
    beat_key: str
    track: str
    kind: str
    text: str
    reason: str


class CoverageHintOut(BaseModel):
    rule_id: str
    source: str


class CoverageSlotOut(BaseModel):
    """整個遊戲一支影片：一格（開局、走完一輪、獲勝方式）的涵蓋檢查。"""

    slot: str
    title: str
    status: Literal["done", "not_done"]
    reason: str | None
    total_rules: int
    issues: list[CoverageIssueOut]
    problems: list[CoverageProblemOut]
    hints: list[CoverageHintOut]


class DraftCoverageOut(BaseModel):
    # done＝有結果；not_done＝沒做成（reason；整個遊戲時任一格沒做成）；stale＝草稿在檢查後改過
    status: Literal["done", "not_done", "stale"]
    reason: str | None
    # 合計（整個遊戲時是三格加起來，rule_id 前面加格的 key，例如 round-R1）
    total_rules: int
    issues: list[CoverageIssueOut]
    problems: list[CoverageProblemOut]
    hints: list[CoverageHintOut]
    # 依格的摘要；單章專案是空的
    slots: list[CoverageSlotOut] = []


class DraftTermsOut(BaseModel):
    status: Literal["used", "empty", "missing"]
    message: str | None


class VideoDraftOut(BaseModel):
    video_version: int
    segments: list[DraftSegmentOut]
    assets: list[DraftAssetOut]
    coverage: DraftCoverageOut
    terms: DraftTermsOut
    # 頁面文字在草稿產生後被改過
    pages_stale: bool
    pages_stale_message: str | None


# --------------------------------------------------------------------------- 素材（MR 7）

# 照片需要順時針轉幾度才會擺正
Orientation = Literal[0, 90, 180, 270]


def _check_box(name: str, box: list[float] | None) -> None:
    """區域座標 [x, y, w, h]：0–1 的相對比例，以套用方向之後的圖為準。"""
    if box is None:
        return
    if len(box) != 4:
        raise ValueError(f"區域 {name} 必須是 [x, y, w, h] 四個數字")
    x, y, w, h = box
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 + 1e-9 or y + h > 1 + 1e-9:
        raise ValueError(f"區域 {name} 超出 0–1 的範圍：{box}")


class SegmentAssetSwapIn(BaseModel):
    """換某一段某一格的素材（2026-11-25 永傑決定；完整版也支援放牌的格子）。"""

    # 要換的格子（main、sidebar）；文字格子不能換
    slot: str
    # 換成哪個素材：必須在素材清單裡，而且不是繪製、沒有略過
    asset_key: str
    # 放牌的格子：換哪一張（item_key）的正面（front）或牌背（back）；單一素材的格子不用給
    item_key: str | None = None
    face: Literal["front", "back"] = "front"
    # 店員看到的段資料版本；和目前的不同時 409，避免蓋掉別人的修改
    video_version: int


class SegmentAssetSwapOut(BaseModel):
    segment_key: str
    slot: str
    # 放牌的格子換的是哪一張、正面或牌背；單一素材的格子 item_key 是 null
    item_key: str | None
    face: Literal["front", "back"]
    old_asset_key: str
    new_asset_key: str
    # 新素材上要重標的區域（沿用自舊素材、還沒有座標）；框線、標籤、動作都保留
    regions_to_mark: list[str]
    # 換完之後沒有段在用的素材：不用再拍
    unused_assets: list[str]
    video_version: int


class VideoAssetCreate(BaseModel):
    """新增一個照片素材（店員換素材時，正確的素材不在清單裡；2026-11-25）。"""

    # 給店員看的中文名稱，不可和既有素材相同
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    # 拍攝說明（選填），例如「整張牌正面朝上，從正上方拍」
    shot: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    # 店員看到的段資料版本；和目前的不同時 409
    video_version: int


class VideoAssetUpdate(BaseModel):
    """改方向或區域（沒給的欄位不變）。區域給 null 代表改回待量測。

    只改方向、沒有同時給區域時，所有區域改回待量測（座標是以套用方向之後的圖為準）。
    """

    orientation: Orientation | None = None
    regions: dict[str, list[float] | None] | None = None
    # 略過這個素材（true）或取消略過（false）；只靠它的段不能略過（MR 9）
    skipped: bool | None = None
    # 照片拍不到的區域（整份取代；[] 取消全部）。產生影片時拿掉指向它們的框選、標籤與移動
    skipped_regions: list[str] | None = None

    @model_validator(mode="after")
    def _regions_in_range(self) -> "VideoAssetUpdate":
        for name, box in (self.regions or {}).items():
            _check_box(name, box)
        return self


class VideoAssetOut(BaseModel):
    asset_key: str
    # 給店員看的中文名稱；舊的草稿沒有時是 null
    label: str | None = None
    kind: str
    priority: str
    reason: str
    shot: str | None
    has_photo: bool
    orientation: int
    # 區域名稱 → [x, y, w, h]；null＝待量測
    regions: dict[str, list[float] | None]
    # 區域名稱 → 給店員的白話說明（只在標區域畫面顯示，不進影片）；舊的草稿沒有
    region_hints: dict[str, str] = {}
    # 區域名稱 → 用到它的段（段號從 1 開始）
    region_segments: dict[str, list[int]] = {}
    # 照片拍不到、店員略過的區域
    skipped_regions: list[str] = []
    # 寫入後的段資料版本
    video_version: int
    # 店員略過這個素材（MR 9）
    skipped: bool = False
    # 可以略過：略過後每一段仍有主要內容（程式判斷，不看 priority）
    skippable: bool = False
    # 略過後會少一張圖的段（段號從 1 開始）
    skip_affected_segments: list[int] = []
    # 只靠這張素材、所以不能略過的段
    skip_blocked_segments: list[int] = []


class MissingPhotoOut(BaseModel):
    asset_key: str
    # 給店員看的名稱（中文名稱；舊的草稿用 reason）
    label: str = ""

    # AI 標的 must／optional；可不可以略過改看 skippable
    # （沒有照片都會擋住產生影片，第 1 階段的限制）
    priority: str
    # 可以略過：略過後每一段仍有主要內容（程式判斷）
    skippable: bool = False
    reason: str
    shot: str | None
    # 略過後會少一張圖的段、只靠它而不能略過的段（MR 9）
    skip_affected_segments: list[int] = []
    skip_blocked_segments: list[int] = []


class MissingRegionOut(BaseModel):
    asset_key: str
    region: str


class UnsupportedAssetOut(BaseModel):
    asset_key: str
    kind: str
    message: str


class VideoReadinessOut(BaseModel):
    """產生影片前還缺什麼；三個清單都是空的才 ready。"""

    ready: bool
    missing_photos: list[MissingPhotoOut]
    missing_regions: list[MissingRegionOut]
    unsupported: list[UnsupportedAssetOut]


# --------------------------------------------------------------------------- 成品影片（MR 9）


class RenderSegmentOut(BaseModel):
    segment_key: str
    # 這一段第一句開始的秒數（點一段跳到這裡）
    start_seconds: float
    # 第一句字幕，段清單上顯示
    title: str


class VideoRenderOut(BaseModel):
    """最近一次成功產生的影片。"""

    job_id: uuid.UUID
    # 讀影片檔的路徑（帶身分讀取）
    video_path: str
    total_seconds: float
    # 這次重新編碼的段、沿用快取的段
    reencoded: list[str]
    reused: list[str]
    # 略過的選拍素材
    skipped_assets: list[str]
    # 沒有設定文字轉語音時，旁白靜音、時間為估計值
    estimated: bool
    warnings: list[str]
    # 段清單；這個欄位加上之前產生的影片是空的
    segments: list[RenderSegmentOut] = []
    finished_at: datetime | None
