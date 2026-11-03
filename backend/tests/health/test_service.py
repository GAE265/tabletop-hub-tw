from sqlalchemy.exc import OperationalError

from app.domains.health.service import HealthService


class FakeRepository:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    def ping(self) -> None:
        if self.fail:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_service_reports_ok_when_ping_succeeds() -> None:
    result = HealthService(FakeRepository(fail=False)).check()
    assert (result.status, result.database) == ("ok", "up")


def test_service_reports_degraded_when_ping_fails() -> None:
    result = HealthService(FakeRepository(fail=True)).check()
    assert (result.status, result.database) == ("degraded", "down")
