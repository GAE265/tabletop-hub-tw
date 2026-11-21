"""規則教學與問答 API 的請求與回應格式（spec rules-qa）。"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

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
    # 目前步驟：不存欄位，由專案的狀態推出。MR 1 沒有其他狀態，固定是 pages（上傳規則書）
    step: Literal["pages"]
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
