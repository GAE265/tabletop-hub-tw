from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


class SessionRepository:
    """共用同一個 session 的 repository。交易的範圍由 service 用 transaction() 決定。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """一個交易：區塊正常結束就提交；拋出例外就全部退回，什麼都不寫。"""
        try:
            yield
        except BaseException:
            self.session.rollback()
            raise
        self.session.commit()
