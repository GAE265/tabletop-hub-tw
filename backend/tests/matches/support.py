"""matches API 測試共用的輔助函式。"""

from typing import Any

BASE = "/api/v1/matches"


def match_body(game_id: int, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "game_id": game_id,
        "played_on": "2026-11-20",
        "location_type": "home",
    }
    body.update(overrides)
    return body


def game_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "played_seat_numbers": [1, 2],
        "double_blade_count": 1,
        "dark_blade_count": 1,
        "giant_blade_count": 0,
        "faithful_count": 2,
        "has_white_rose": False,
    }
    data.update(overrides)
    return data


def turn_body(turn_number: int = 1, seat_number: int = 1, **data_overrides: Any) -> dict[str, Any]:
    return {
        "turn_number": turn_number,
        "seat_number": seat_number,
        "game_data": game_data(**data_overrides),
    }


def result_body(winning: str = "rose", factions: dict[int, str] | None = None) -> dict[str, Any]:
    factions = factions or {1: "rose", 2: "rose", 3: "blood_blade", 4: "blood_blade"}
    return {
        "winning_faction": winning,
        "participants": [{"seat_number": s, "faction": f} for s, f in factions.items()],
    }


def error_code(response) -> str:
    return response.json()["error"]["code"]


def participant_named(match: dict[str, Any], display_name: str) -> dict[str, Any]:
    return next(p for p in match["participants"] if p["display_name"] == display_name)
