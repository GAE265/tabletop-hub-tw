from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.domains.rules_ingest.repository import ManualPageRepository
from app.domains.rules_ingest.schemas import ManualPageListOut, ManualPageOut
from app.domains.rules_ingest.service import MAX_IMAGE_BYTES, ManualPagesService
from app.domains.rules_qa.router import get_rules_qa_service
from app.domains.rules_qa.service import RulesQaService
from app.integrations.ocr.base import VisionProvider

router = APIRouter(prefix="/games/{games_id}/manual-pages", tags=["rules_ingest"])


def get_vision(request: Request) -> VisionProvider:
    return request.app.state.vision


def get_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    vision: Annotated[VisionProvider, Depends(get_vision)],
    qa_service: Annotated[RulesQaService, Depends(get_rules_qa_service)],
) -> ManualPagesService:
    return ManualPagesService(
        ManualPageRepository(session),
        GameRepository(session),
        vision,
        request.app.state.settings.ocr_provider,
        reindex=qa_service.index_page,
    )


@router.put("/{page}", response_model=ManualPageOut)
def import_page(
    games_id: int,
    page: Annotated[int, Path(ge=1)],
    file: Annotated[UploadFile, File()],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ManualPagesService, Depends(get_service)],
) -> ManualPageOut:
    # 有界讀取：只多讀一個位元組，讓 service 辨識超過上限，避免整份大檔載入記憶體。
    image = file.file.read(MAX_IMAGE_BYTES + 1)
    return service.import_page(user, games_id, page, image)


@router.get("", response_model=ManualPageListOut)
def list_pages(
    games_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ManualPagesService, Depends(get_service)],
) -> ManualPageListOut:
    return service.list_pages(user, games_id)
