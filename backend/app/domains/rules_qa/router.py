"""規則教學與問答 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.domains.booking.repository import BookingRepository
from app.domains.rules_qa.repository import (
    RulesQaRepository,
    VideoJobRepository,
    VideoProjectRepository,
    VideoTermsRepository,
)
from app.domains.rules_qa.schemas import (
    MessageRequest,
    MessageResponse,
    RulesLessonList,
    RulesLessonOut,
    VideoJobList,
    VideoJobOut,
    VideoOut,
    VideoProjectCreate,
    VideoProjectList,
    VideoProjectOut,
    VideoRequest,
    VideoTermsIn,
    VideoTermsOut,
)
from app.domains.rules_qa.service import (
    RulesQaService,
    VideoJobService,
    VideoProjectService,
    VideoTermsService,
)

router = APIRouter(prefix="/rules-lessons", tags=["rules_qa"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_rules_qa_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> RulesQaService:
    """LLM 與 embedding 用後端啟動時建立的 provider（main.py）；測試會換成 fake。"""
    state = request.app.state
    return RulesQaService(
        RulesQaRepository(session),
        embedding=state.rules_qa_embedding,
        embedding_model=state.rules_qa_embedding_model,
        llm=state.llm,
    )


ServiceDep = Annotated[RulesQaService, Depends(get_rules_qa_service)]


@router.get("", response_model=RulesLessonList)
def list_lessons(user: CurrentUserDep, service: ServiceDep) -> RulesLessonList:
    """有教材（規則書或教學影片）的遊戲。"""
    return service.list_lessons(user)


@router.get("/{game_id}", response_model=RulesLessonOut)
def get_lesson(game_id: int, user: CurrentUserDep, service: ServiceDep) -> RulesLessonOut:
    """某款遊戲的教學內容：教學影片（有的話）、是否有規則書、建議問題。"""
    return service.get_lesson(user, game_id)


@router.put("/{game_id}/video", response_model=VideoOut)
def set_video(
    game_id: int, body: VideoRequest, user: CurrentUserDep, service: ServiceDep
) -> VideoOut:
    """設定或取代這款遊戲的教學影片（YouTube 網址）。限店家人員與管理員。"""
    return service.set_video(user, game_id, body)


@router.post(
    "/{game_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def send_message(
    game_id: int, body: MessageRequest, user: CurrentUserDep, service: ServiceDep
) -> MessageResponse:
    """規則問答：從這款遊戲的規則書找答案，回答附規則書頁碼；可以帶上一則的 response_id 追問。"""
    return service.send_message(user, game_id, body)


# --------------------------------------------------------------------------- 規則影片專案

videos_router = APIRouter(prefix="/rules-videos", tags=["rules_qa"])


def get_video_project_service(
    session: Annotated[Session, Depends(get_session)],
) -> VideoProjectService:
    # 店家是共用表 booking_shops，由擁有者的 repository 查詢（AGENTS.md 4.2 共用資料表例外）
    return VideoProjectService(
        VideoProjectRepository(session), RulesQaRepository(session), BookingRepository(session)
    )


VideoServiceDep = Annotated[VideoProjectService, Depends(get_video_project_service)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@videos_router.post("", response_model=VideoProjectOut, status_code=status.HTTP_201_CREATED)
def create_video_project(
    body: VideoProjectCreate, user: CurrentUserDep, service: VideoServiceDep
) -> VideoProjectOut:
    """建立規則影片專案（一個專案一章）。限店家人員與管理員；管理員要指定店家。"""
    return service.create(user, body)


@videos_router.get("", response_model=VideoProjectList)
def list_video_projects(
    user: CurrentUserDep, service: VideoServiceDep, page: Page = 1, page_size: PageSize = 20
) -> VideoProjectList:
    """店家人員看自己店的專案，管理員看全部；依最後修改時間由新到舊。"""
    return service.list(user, page, page_size)


@videos_router.get("/{project_id}", response_model=VideoProjectOut)
def get_video_project(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoServiceDep
) -> VideoProjectOut:
    """查看一個影片專案；別家店的專案回 404。"""
    return service.get(user, project_id)


def get_video_job_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoJobService:
    """建立工作時通知背景執行緒（後端啟動時建立；RULES_VIDEO_WORKER=false 時沒有）。"""
    runner = getattr(request.app.state, "rules_video_runner", None)
    return VideoJobService(
        VideoJobRepository(session),
        VideoProjectRepository(session),
        notify=runner.notify if runner is not None else None,
    )


VideoJobServiceDep = Annotated[VideoJobService, Depends(get_video_job_service)]


@videos_router.get("/{project_id}/jobs", response_model=VideoJobList)
def list_video_jobs(
    project_id: uuid.UUID,
    user: CurrentUserDep,
    service: VideoJobServiceDep,
    page: Page = 1,
    page_size: PageSize = 20,
) -> VideoJobList:
    """專案的工作，新的在前；店員離開再回來時，看第一筆就知道最近的工作做到哪裡。"""
    return service.list(user, project_id, page, page_size)


@videos_router.get("/{project_id}/jobs/{job_id}", response_model=VideoJobOut)
def get_video_job(
    project_id: uuid.UUID, job_id: uuid.UUID, user: CurrentUserDep, service: VideoJobServiceDep
) -> VideoJobOut:
    """一個工作的狀態、進度、說明、失敗原因與結果。"""
    return service.get(user, project_id, job_id)


# --------------------------------------------------------------------------- 規則影片的用語對照表

video_terms_router = APIRouter(prefix="/games/{game_id}/video-terms", tags=["rules_qa"])


def get_video_terms_service(
    session: Annotated[Session, Depends(get_session)],
) -> VideoTermsService:
    return VideoTermsService(VideoTermsRepository(session), RulesQaRepository(session))


VideoTermsServiceDep = Annotated[VideoTermsService, Depends(get_video_terms_service)]


@video_terms_router.put("", response_model=VideoTermsOut)
def replace_video_terms(
    game_id: int, body: VideoTermsIn, user: CurrentUserDep, service: VideoTermsServiceDep
) -> VideoTermsOut:
    """上傳這款遊戲的用語對照表（整份取代）。只限管理員；空陣列代表確認不使用對照表。"""
    return service.replace(user, game_id, body)


@video_terms_router.get("", response_model=VideoTermsOut)
def get_video_terms(
    game_id: int, user: CurrentUserDep, service: VideoTermsServiceDep
) -> VideoTermsOut:
    """這款遊戲的用語對照表；從未上傳回 404（與上傳空表不同）。"""
    return service.get(user, game_id)
