import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(make_settings):
    app = create_app(make_settings())
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("error_type", range(1, 11))
def test_error_log_endpoint_triggers_expected_failure(
    client: TestClient, error_type: int, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    response = client.post(f"/api/v1/dev/error-logs/{error_type}")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    expected = f"error type {error_type}"
    records = [
        record
        for record in caplog.records
        if expected in record.getMessage()
        or (record.exc_info and expected in str(record.exc_info[1]))
    ]
    assert records
    if error_type <= 5:
        assert any(record.name == "app.core.errors" and record.exc_info for record in records)
    if error_type in {6, 7, 8}:
        assert any(record.exc_info for record in records)
    if error_type in {9, 10}:
        assert all(record.exc_info is None for record in records)


def test_error_log_endpoint_rejects_out_of_range_type(client: TestClient) -> None:
    for error_type in (0, 11):
        response = client.post(f"/api/v1/dev/error-logs/{error_type}")
        assert response.status_code == 422


def test_error_log_endpoint_is_unavailable_in_jwt_mode(make_settings) -> None:
    client = TestClient(create_app(make_settings(auth_mode="jwt")))

    response = client.post("/api/v1/dev/error-logs/1")

    assert response.status_code == 404
