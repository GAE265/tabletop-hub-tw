from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.domains.health.repository import HealthRepository
from app.domains.health.schemas import HealthResponse
from app.domains.health.service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def get_health(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    return HealthService(HealthRepository(session)).check()
