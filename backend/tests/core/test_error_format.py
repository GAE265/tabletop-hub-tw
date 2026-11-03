from fastapi.testclient import TestClient

from app.core.auth import CurrentUser


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)
    return body["error"]


def test_unknown_path_is_404(client: TestClient) -> None:
    assert_error(client.get("/api/v1/nope"), 404, "NOT_FOUND")


def test_wrong_method_is_405(client: TestClient) -> None:
    assert_error(client.post("/_probe/me"), 405, "METHOD_NOT_ALLOWED")


def test_validation_error_is_422_with_fields(client: TestClient) -> None:
    error = assert_error(client.get("/_probe/items", params={"n": "abc"}), 422, "VALIDATION_ERROR")
    assert any("n" in item["loc"] for item in error["details"]["errors"])


def test_unhandled_exception_is_500_without_leaking(client: TestClient) -> None:
    response = client.get("/_probe/boom")
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "super-secret-internal-detail" not in response.text


def test_permission_denied_is_403(client: TestClient, as_player: CurrentUser) -> None:
    assert_error(client.get("/_probe/admin-only"), 403, "PERMISSION_DENIED")


def test_app_error_keeps_custom_code_and_details(client: TestClient) -> None:
    error = assert_error(client.get("/_probe/conflict"), 409, "BOOKING_TABLE_TAKEN")
    assert error["details"] == {"table_id": "t1"}
