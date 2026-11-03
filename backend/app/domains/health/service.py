from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.domains.health.schemas import HealthResponse


class Pingable(Protocol):
    def ping(self) -> None: ...


class HealthService:
    def __init__(self, repository: Pingable) -> None:
        self.repository = repository

    def check(self) -> HealthResponse:
        try:
            self.repository.ping()
        except SQLAlchemyError:
            return HealthResponse(status="degraded", database="down")
        return HealthResponse(status="ok", database="up")
