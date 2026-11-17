"""規則教學與問答 API 的請求與回應格式（spec rules-qa）。"""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

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
