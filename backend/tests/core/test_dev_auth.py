import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, require_role
from app.core.config import Settings
from app.core.errors import PermissionDenied
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_STAFF

SOME_ID = "12345678-1234-4234-8234-123456789abc"


SHOP_ID = "87654321-4321-4321-8321-cba987654321"


def test_player_header_has_no_shop(client: TestClient) -> None:
    response = client.get("/_probe/me", headers={"X-Dev-User": f"{SOME_ID}:player"})
    assert response.status_code == 200
    assert response.json() == {"id": SOME_ID, "role": "player", "shop_id": ""}


def test_shop_staff_header_with_shop(client: TestClient) -> None:
    response = client.get("/_probe/me", headers={"X-Dev-User": f"{SOME_ID}:shop_staff:{SHOP_ID}"})
    assert response.status_code == 200
    assert response.json() == {"id": SOME_ID, "role": "shop_staff", "shop_id": SHOP_ID}


@pytest.mark.parametrize(
    "value",
    [
        f"{SOME_ID}:shop_staff",  # shop_staff 缺店家
        f"{SOME_ID}:shop_staff:",  # 第三段為空
        f"{SOME_ID}:shop_staff:not-a-uuid",  # 店家不是 UUID
        f"{SOME_ID}:player:{SHOP_ID}",  # player 多帶店家
        f"{SOME_ID}:admin:{SHOP_ID}",  # admin 多帶店家
        f"{SOME_ID}:shop_staff:{SHOP_ID}:extra",  # 段數過多
    ],
)
def test_shop_segment_rules_are_enforced(client: TestClient, value: str) -> None:
    response = client.get("/_probe/me", headers={"X-Dev-User": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DEV_USER"


def test_current_user_does_not_need_the_database(client: TestClient) -> None:
    """測試用 app 指向連不上的資料庫；取得身分不得查任何資料表。"""
    response = client.get("/_probe/me", headers={"X-Dev-User": f"{SOME_ID}:shop_staff:{SHOP_ID}"})
    assert response.status_code == 200


def test_header_sets_current_user(client: TestClient) -> None:
    # 契約變更：shop_staff 必須帶 :<shop_uuid>（原本不帶店家的寫法現在是 400）
    response = client.get("/_probe/me", headers={"X-Dev-User": f"{SOME_ID}:shop_staff:{SHOP_ID}"})
    assert response.status_code == 200
    assert response.json()["id"] == SOME_ID
    assert response.json()["role"] == "shop_staff"


def test_no_header_uses_default_player(client: TestClient, make_settings) -> None:
    response = client.get("/_probe/me")
    assert response.status_code == 200
    assert response.json()["id"] == str(make_settings().dev_default_user_id)
    assert response.json()["role"] == "player"


def test_default_player_id_comes_from_settings(make_settings) -> None:
    custom = uuid.uuid4()
    assert make_settings(dev_default_user_id=custom).dev_default_user_id == custom


@pytest.mark.parametrize(
    "value",
    ["7:player", "abc", f"{SOME_ID}:organizer", f"{SOME_ID}:", ":player", f"{SOME_ID}:player:x"],
)
def test_bad_header_is_400(client: TestClient, value: str) -> None:
    response = client.get("/_probe/me", headers={"X-Dev-User": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DEV_USER"


def test_jwt_mode_ignores_dev_header(jwt_client: TestClient) -> None:
    response = jwt_client.get("/_probe/me", headers={"X-Dev-User": f"{SOME_ID}:admin"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_require_role_passes_when_allowed() -> None:
    require_role(CurrentUser(id=uuid.uuid4(), role="player"), "player", "admin")


def test_require_role_raises_when_not_allowed() -> None:
    with pytest.raises(PermissionDenied):
        require_role(CurrentUser(id=uuid.uuid4(), role="player"), "shop_staff", "admin")


def test_as_shop_staff_has_shop_id(client: TestClient, as_shop_staff: CurrentUser) -> None:
    body = client.get("/_probe/me").json()
    assert body["role"] == "shop_staff"
    assert body["shop_id"] == str(TEST_SHOP_STAFF.shop_id)


def test_as_admin_passes_admin_only(client: TestClient, as_admin: CurrentUser) -> None:
    assert client.get("/_probe/me").json()["id"] == str(TEST_ADMIN.id)
    assert client.get("/_probe/admin-only").status_code == 200


def test_as_player_has_no_shop(client: TestClient, as_player: CurrentUser) -> None:
    body = client.get("/_probe/me").json()
    assert body["id"] == str(TEST_PLAYER.id)
    assert body["shop_id"] == ""


def test_settings_default_auth_mode_is_not_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_MODE", raising=False)  # CI 會用環境變數設成 dev
    assert Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/d").auth_mode == "jwt"
