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
    game_id: int
    chapter_number: Annotated[int, Field(ge=1)]
    chapter_title: ChapterTitle
    # 店家人員不用填（用登入身分的店家，填別家店回 403）；管理員必填
    shop_id: uuid.UUID | None = None


class VideoProjectOut(BaseModel):
    id: uuid.UUID
    game_id: int
    game_name: str
    shop_id: uuid.UUID
    created_by: uuid.UUID
    chapter_number: int
    chapter_title: str
    # 目前步驟：不存欄位，由專案的狀態推出（design.md D1、D11）：
    # pages＝還沒有草稿（上傳規則書、選頁、編輯文字）；draft＝有草稿
    step: Literal["pages", "draft"]
    created_at: datetime
    updated_at: datetime


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
    """建立工作。本 MR 只開放 draft；render、revise 在之後的 MR 加上。"""

    kind: Literal["draft"]


class DraftBeatOut(BaseModel):
    beat_key: str
    narration: str
    subtitle: str


class DraftSegmentOut(BaseModel):
    segment_key: str
    source_pages: list[int]
    beats: list[DraftBeatOut]


class DraftAssetOut(BaseModel):
    asset_key: str
    kind: str
    priority: str
    reason: str
    shot: str | None
    # 泛稱的素材：reason 寫了「代表牌」，店員可以換成同類的任一張牌
    representative: bool
    regions: list[str]
    has_photo: bool


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


class DraftCoverageOut(BaseModel):
    # done＝有結果；not_done＝沒做成（reason）；stale＝草稿在檢查後改過
    status: Literal["done", "not_done", "stale"]
    reason: str | None
    total_rules: int
    issues: list[CoverageIssueOut]
    problems: list[CoverageProblemOut]
    hints: list[CoverageHintOut]


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


class VideoAssetUpdate(BaseModel):
    """改方向或區域（沒給的欄位不變）。區域給 null 代表改回待量測。

    只改方向、沒有同時給區域時，所有區域改回待量測（座標是以套用方向之後的圖為準）。
    """

    orientation: Orientation | None = None
    regions: dict[str, list[float] | None] | None = None

    @model_validator(mode="after")
    def _regions_in_range(self) -> "VideoAssetUpdate":
        for name, box in (self.regions or {}).items():
            _check_box(name, box)
        return self


class VideoAssetOut(BaseModel):
    asset_key: str
    kind: str
    priority: str
    reason: str
    shot: str | None
    has_photo: bool
    orientation: int
    # 區域名稱 → [x, y, w, h]；null＝待量測
    regions: dict[str, list[float] | None]
    # 寫入後的段資料版本
    video_version: int


class MissingPhotoOut(BaseModel):
    asset_key: str
    # must＝必拍、optional＝選拍（選拍沒有照片也會擋住產生影片，第 1 階段的限制）
    priority: str
    reason: str
    shot: str | None


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
