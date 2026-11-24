"""規則教學與問答 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.domains.booking.repository import BookingRepository
from app.domains.rules_ingest.repository import ManualPageRepository
from app.domains.rules_ingest.service import read_manual_pages
from app.domains.rules_qa.repository import (
    RulesQaRepository,
    VideoDraftRepository,
    VideoJobRepository,
    VideoPagesRepository,
    VideoProjectRepository,
    VideoTermsRepository,
)
from app.domains.rules_qa.schemas import (
    MessageRequest,
    MessageResponse,
    RulebookOut,
    RulesLessonList,
    RulesLessonOut,
    SegmentAssetSwapIn,
    SegmentAssetSwapOut,
    VideoAssetCreate,
    VideoAssetOut,
    VideoAssetUpdate,
    VideoDraftOut,
    VideoJobCreate,
    VideoJobList,
    VideoJobOut,
    VideoOut,
    VideoPagesIn,
    VideoPagesOut,
    VideoProjectCreate,
    VideoProjectList,
    VideoProjectOut,
    VideoReadinessOut,
    VideoRenderOut,
    VideoRequest,
    VideoTermsIn,
    VideoTermsOut,
)
from app.domains.rules_qa.service import (
    RulesQaService,
    VideoAssetsService,
    VideoDraftService,
    VideoJobService,
    VideoPagesService,
    VideoProjectService,
    VideoRenderService,
    VideoRulebookService,
    VideoTermsService,
)
from app.domains.rules_qa.video_assets import MAX_PHOTO_BYTES

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
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoProjectService:
    # 店家是共用表 booking_shops，由擁有者的 repository 查詢（AGENTS.md 4.2 共用資料表例外）；
    # 規則書原文用 rules_ingest 的 service 函式讀（domain 之間只呼叫對方的 service）
    manual = ManualPageRepository(session)
    return VideoProjectService(
        VideoProjectRepository(session),
        RulesQaRepository(session),
        BookingRepository(session),
        read_pages=lambda game_id: read_manual_pages(manual, game_id),
        pages=VideoPagesRepository(session),
        drafts=get_video_job_service(request, session),
        jobs=VideoJobRepository(session),
        storage=request.app.state.storage,
        work_dir=Path(request.app.state.settings.rules_video_work_dir),
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


@videos_router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video_project(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoServiceDep
) -> Response:
    """刪除影片專案：資料庫的專案與工作紀錄、存放空間的照片與成品影片、工作資料夾一起刪除，
    無法復原。同店店員與管理員可以刪；有進行中的工作時 409。"""
    service.delete(user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


# --------------------------------------------------------------------------- 規則書頁面文字


def get_video_pages_service(
    session: Annotated[Session, Depends(get_session)],
) -> VideoPagesService:
    # 原文用 rules_ingest 的 service 函式讀（AGENTS.md 4.2：domain 之間只呼叫對方的 service）
    manual = ManualPageRepository(session)
    return VideoPagesService(
        VideoPagesRepository(session),
        VideoProjectRepository(session),
        lambda game_id: read_manual_pages(manual, game_id),
    )


VideoPagesServiceDep = Annotated[VideoPagesService, Depends(get_video_pages_service)]


@videos_router.get("/{project_id}/pages", response_model=VideoPagesOut)
def get_video_pages(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoPagesServiceDep
) -> VideoPagesOut:
    """可選的頁、選了的本章頁與參考頁、每頁的原文與編輯後的文字、刪掉的段落與改過的行。"""
    return service.get(user, project_id)


@videos_router.put("/{project_id}/pages", response_model=VideoPagesOut)
def replace_video_pages(
    project_id: uuid.UUID, body: VideoPagesIn, user: CurrentUserDep, service: VideoPagesServiceDep
) -> VideoPagesOut:
    """選本章頁與參考頁、存編輯後的文字（整份取代；沒給文字的頁用原文）。不改 games_manual。"""
    return service.replace(user, project_id, body)


# --------------------------------------------------------------------------- 草稿


def get_video_draft_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoDraftService:
    return VideoDraftService(
        VideoDraftRepository(session),
        VideoProjectRepository(session),
        VideoTermsRepository(session),
        get_video_job_service(request, session),
    )


VideoDraftServiceDep = Annotated[VideoDraftService, Depends(get_video_draft_service)]


@videos_router.post(
    "/{project_id}/jobs", response_model=VideoJobOut, status_code=status.HTTP_202_ACCEPTED
)
def create_video_job(
    project_id: uuid.UUID,
    body: VideoJobCreate,
    user: CurrentUserDep,
    service: VideoDraftServiceDep,
) -> VideoJobOut:
    """建立工作：draft＝依編輯後的頁面文字產生草稿；render＝產生影片（素材要齊）。回 202。"""
    return service.start(user, project_id, body.kind)


@videos_router.get("/{project_id}/draft", response_model=VideoDraftOut)
def get_video_draft(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoDraftServiceDep
) -> VideoDraftOut:
    """草稿：每段的句子、素材清單、涵蓋檢查摘要、用語對照表狀態、是否依舊文字產生。"""
    return service.get(user, project_id)


# --------------------------------------------------------------------------- 素材


def get_video_assets_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoAssetsService:
    """存放介面用後端啟動時建立的（main.py 的 app.state.storage）；測試是 FakeFileStorage。"""
    return VideoAssetsService(
        VideoDraftRepository(session), VideoProjectRepository(session), request.app.state.storage
    )


VideoAssetsServiceDep = Annotated[VideoAssetsService, Depends(get_video_assets_service)]


@videos_router.put("/{project_id}/assets/{asset_key}/photo", response_model=VideoAssetOut)
def upload_video_asset_photo(
    project_id: uuid.UUID,
    asset_key: str,
    file: Annotated[UploadFile, File()],
    user: CurrentUserDep,
    service: VideoAssetsServiceDep,
) -> VideoAssetOut:
    """上傳或換一張素材照片（JPEG、PNG，最多 15 MB；依 EXIF 轉正）。方向改回 0，區域座標保留。"""
    # 有界讀取：只多讀一個位元組，讓 service 辨識超過上限
    data = file.file.read(MAX_PHOTO_BYTES + 1)
    return service.upload_photo(user, project_id, asset_key, data)


@videos_router.get("/{project_id}/assets/{asset_key}/photo")
def read_video_asset_photo(
    project_id: uuid.UUID, asset_key: str, user: CurrentUserDep, service: VideoAssetsServiceDep
) -> Response:
    """素材照片的圖檔（帶身分讀取，權限同專案）。"""
    data, content_type = service.read_photo(user, project_id, asset_key)
    return Response(content=data, media_type=content_type)


@videos_router.get("/{project_id}/assets/{asset_key}", response_model=VideoAssetOut)
def get_video_asset(
    project_id: uuid.UUID, asset_key: str, user: CurrentUserDep, service: VideoAssetsServiceDep
) -> VideoAssetOut:
    """一個素材的方向、區域座標、有沒有照片。"""
    return service.get_asset(user, project_id, asset_key)


@videos_router.patch("/{project_id}/assets/{asset_key}", response_model=VideoAssetOut)
def update_video_asset(
    project_id: uuid.UUID,
    asset_key: str,
    body: VideoAssetUpdate,
    user: CurrentUserDep,
    service: VideoAssetsServiceDep,
) -> VideoAssetOut:
    """改方向或區域座標；只改方向時區域改回待量測。"""
    return service.update_asset(user, project_id, asset_key, body)


@videos_router.patch("/{project_id}/segments/{segment_key}", response_model=SegmentAssetSwapOut)
def swap_video_segment_asset(
    project_id: uuid.UUID,
    segment_key: str,
    body: SegmentAssetSwapIn,
    user: CurrentUserDep,
    service: VideoAssetsServiceDep,
) -> SegmentAssetSwapOut:
    """換某一段某一格的素材（放牌的格子指定哪一張的正面或牌背）；只能換成清單裡可以用的素材。
    框線、標籤、動作都保留，區域沿用到新素材，回應列出要重標的區域；版本不同時 409。"""
    return service.swap_segment_asset(user, project_id, segment_key, body)


@videos_router.post(
    "/{project_id}/assets", response_model=VideoAssetOut, status_code=status.HTTP_201_CREATED
)
def create_video_asset(
    project_id: uuid.UUID,
    body: VideoAssetCreate,
    user: CurrentUserDep,
    service: VideoAssetsServiceDep,
) -> VideoAssetOut:
    """新增一個照片素材（中文名稱、拍攝說明），之後可以換到某一段並拍照。同名時 422。"""
    return service.create_asset(user, project_id, body)


@videos_router.get("/{project_id}/readiness", response_model=VideoReadinessOut)
def get_video_readiness(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoAssetsServiceDep
) -> VideoReadinessOut:
    """產生影片前還缺什麼：沒有照片的素材、沒有座標的區域、本版不支援的繪製素材。"""
    return service.readiness(user, project_id)


# --------------------------------------------------------------------------- 成品影片


def get_video_render_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoRenderService:
    return VideoRenderService(
        VideoProjectRepository(session), VideoJobRepository(session), request.app.state.storage
    )


VideoRenderServiceDep = Annotated[VideoRenderService, Depends(get_video_render_service)]


@videos_router.get("/{project_id}/render", response_model=VideoRenderOut)
def get_video_render(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoRenderServiceDep
) -> VideoRenderOut:
    """最近一次成功產生的影片：總長、重新編碼與沿用的段、略過的素材、產生時間。"""
    return service.get(user, project_id)


@videos_router.get("/{project_id}/render/video")
def read_video_render(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoRenderServiceDep
) -> Response:
    """影片檔（帶身分讀取，權限同專案；整支讀出，見 design.md D13 待決 1）。"""
    return Response(content=service.video(user, project_id), media_type="video/mp4")


# --------------------------------------------------------------------------- 店員拍規則書


def get_video_rulebook_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> VideoRulebookService:
    """照片放在後端啟動時建立的存放介面（main.py 的 app.state.storage）。"""
    return VideoRulebookService(
        VideoProjectRepository(session), VideoPagesRepository(session), request.app.state.storage
    )


VideoRulebookServiceDep = Annotated[VideoRulebookService, Depends(get_video_rulebook_service)]


@videos_router.get("/{project_id}/rulebook", response_model=RulebookOut)
def get_video_rulebook(
    project_id: uuid.UUID, user: CurrentUserDep, service: VideoRulebookServiceDep
) -> RulebookOut:
    """照片模式專案的規則書照片（依頁的順序）、每張的清晰度、是否都讀過了。"""
    return service.get(user, project_id)


@videos_router.post(
    "/{project_id}/rulebook/photos",
    response_model=RulebookOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_video_rulebook_photo(
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: CurrentUserDep,
    service: VideoRulebookServiceDep,
) -> RulebookOut:
    """加一張規則書照片（排在最後；JPEG、PNG，最多 15 MB；依 EXIF 轉正）。"""
    data = file.file.read(MAX_PHOTO_BYTES + 1)
    return service.upload(user, project_id, data)


@videos_router.get("/{project_id}/rulebook/photos/{index}")
def read_video_rulebook_photo(
    project_id: uuid.UUID, index: int, user: CurrentUserDep, service: VideoRulebookServiceDep
) -> Response:
    """第 index 張規則書照片的圖檔（從 1 開始）。"""
    data, content_type = service.read_photo(user, project_id, index)
    return Response(content=data, media_type=content_type)


@videos_router.delete(
    "/{project_id}/rulebook/photos/{index}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_video_rulebook_photo(
    project_id: uuid.UUID, index: int, user: CurrentUserDep, service: VideoRulebookServiceDep
) -> Response:
    """刪掉第 index 張（後面的往前遞補）。"""
    service.delete(user, project_id, index)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
