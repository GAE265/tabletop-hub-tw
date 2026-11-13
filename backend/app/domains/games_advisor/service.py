"""games_advisor 批次指令的商業邏輯。

目前有共用桌遊資料的三個動作：匯入（spec §8.1）、匯出（§8.10）、同步（§8.11）。
每個動作都是整份檔案一個交易：任何一步不通過就拋 Refused，什麼都不寫。
"""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.domains.games_advisor.repository import GameInUseError, GameRepository
from app.domains.games_advisor.schemas import GamesExport, GamesFile, describe_problems


class Refused(Exception):
    """指令拒絕執行，什麼都沒寫。reasons 是要印給執行的人看的原因，一行一個。"""

    def __init__(self, *reasons: str) -> None:
        super().__init__("\n".join(reasons))
        self.reasons = list(reasons)


@dataclass(frozen=True)
class ImportResult:
    count: int
    # 1–4 號各是哪一款：（id，繁中名稱）
    first_four: list[tuple[int, str]]


@dataclass(frozen=True)
class SyncResult:
    added: int
    updated: int
    deleted: int
    next_id: int


def _validated[FileModel: (GamesFile, GamesExport)](
    model: type[FileModel], data: object, *, id_field: str, type_codes: set[str]
) -> FileModel:
    """照 model 檢查整份檔案；有任何一款不符合就整份拒絕。"""
    try:
        return model.model_validate(data, context={"type_codes": type_codes})
    except ValidationError as exc:
        raise Refused(*describe_problems(exc, data, id_field)) from exc


def _first_four_problems(first_four: list[int], bgg_ids_in_file: set[int]) -> list[str]:
    problems = []
    if len(first_four) != 4:
        problems.append(f"--first-four 要剛好 4 個 bgg_id，收到 {len(first_four)} 個")
    if len(set(first_four)) != len(first_four):
        problems.append("--first-four 有重複的 bgg_id")
    problems += [
        f"--first-four 的 {bgg_id} 不在檔案裡"
        for bgg_id in dict.fromkeys(first_four)
        if bgg_id not in bgg_ids_in_file
    ]
    return problems


def import_games(repository: GameRepository, data: object, first_four: list[int]) -> ImportResult:
    """把 games.json 匯入空的資料庫：first_four 的 4 款依序是 1–4 號，其他照檔案順序。"""
    with repository.transaction():
        games = _validated(
            GamesFile, data, id_field="bgg_id", type_codes=repository.list_game_type_codes()
        ).games
        if problems := _first_four_problems(first_four, {game.bgg_id for game in games}):
            raise Refused(*problems)
        if repository.count_games() > 0:
            raise Refused("資料庫已經有桌遊；要重建請用 GAE265G5 最新的匯出檔執行 sync-games")

        # games 是空的，還沒有任何編號給出去過；計數器設回 1，4 款 Demo 遊戲才會是 1–4 號
        repository.set_next_game_id(1)
        by_bgg_id = {game.bgg_id: game for game in games}
        ordered = [by_bgg_id[bgg_id] for bgg_id in first_four]
        ordered += [game for game in games if game.bgg_id not in first_four]
        imported = []
        for game in ordered:
            game_id = repository.add_game(game.columns())
            repository.replace_game_types(game_id, game.types)
            imported.append((game_id, game.name))
    return ImportResult(count=len(imported), first_four=imported[:4])


def export_games(repository: GameRepository) -> GamesExport:
    """讀出共用桌遊資料與計數器的下一個號碼。只讀，不改任何資料。"""
    with repository.transaction():
        games: list[dict[str, Any]] = repository.list_games()
        if not games:
            raise Refused("資料庫沒有桌遊，沒有東西可以匯出")
        return GamesExport.model_validate({"next_id": repository.next_game_id(), "games": games})


def sync_games(repository: GameRepository, data: object) -> SyncResult:
    """讓資料庫的共用桌遊資料和匯出檔完全一樣，計數器也設成匯出檔的 next_id。"""
    with repository.transaction():
        export = _validated(
            GamesExport, data, id_field="id", type_codes=repository.list_game_type_codes()
        )
        bgg_id_in_database = {game["id"]: game["bgg_id"] for game in repository.list_games()}
        # id 和 bgg_id 都相同才是同一款；其他的（匯出檔沒有的、同 id 但不同款的）先全部刪掉，
        # 再照匯出檔寫入。先刪再寫，bgg_id 才不會和還沒處理到的舊資料撞在一起
        same_game_ids = {
            game.id for game in export.games if bgg_id_in_database.get(game.id) == game.bgg_id
        }
        try:
            deleted = repository.delete_games_except(same_game_ids)
        except GameInUseError as exc:
            raise Refused(
                f"{exc.game_id} 號「{exc.name}」不在匯出檔裡，要刪除，"
                f"但還被資料表 {exc.table} 參照。資料庫沒有任何變動，請找立倫決定怎麼處理"
            ) from exc
        for game in export.games:
            # 同一款只更新欄位、不先刪再寫，參照它的心得摘要、標籤、心得片段才會留著
            repository.save_game(game.id, game.columns())
            repository.replace_game_types(game.id, game.types)
        repository.set_next_game_id(export.next_id)
    return SyncResult(
        added=len(export.games) - len(same_game_ids),
        updated=len(same_game_ids),
        deleted=deleted,
        next_id=export.next_id,
    )
