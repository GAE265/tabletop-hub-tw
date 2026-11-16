"""games_advisor 批次指令的商業邏輯。

- 共用桌遊資料：匯入（spec §8.1）、匯出（§8.10）、同步（§8.11）。整份檔案一個交易：
  任何一步不通過就拋 Refused，什麼都不寫。
- 讀 reviews.json 的指令：心得摘要（§8.3）、心得片段（§8.4）。先檢查整份檔案，不通過就拋
  Refused；通過後一款桌遊一個交易，某款失敗就跳過它、保留它的舊資料，其他款照寫（§7.2）。
- 標籤詞彙表：歸納草稿（§8.5，只寫檔案、不寫資料庫）、同步（§8.6，整份一個交易）。
- 每款桌遊的標籤：上標籤（§8.7，只寫標籤草稿與原始檔）、匯入標籤草稿（§8.8，先檢查整份
  草稿，再一款一個交易）。
"""

import json
from collections.abc import Callable, Collection, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from app.core.games.repository import GameInUseError, GameRepository
from app.domains.games_advisor import prompts
from app.domains.games_advisor.constants import (
    TAG_HIGH_CONFIDENCE,
    TAG_HIGH_CONFIDENCE_MIN_REVIEWS,
    TAG_USAGE_WARNING_RATIO,
    TAG_VOCABULARY_MAX_TAGS,
)
from app.domains.games_advisor.excerpts import DEFAULT_LIMITS, ExcerptLimits, split_reviews
from app.domains.games_advisor.schemas import (
    CandidatesOutput,
    GamesExport,
    GamesFile,
    MergeOutput,
    Review,
    ReviewsFile,
    TagDraftFile,
    TagsOutput,
    TagVocabularyFile,
    describe_problems,
)
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.errors import EmbeddingError
from app.integrations.embedding.factory import EmbeddingConfig
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import LLMOutputRejected, LLMUnavailable


class Refused(Exception):
    """指令拒絕執行，什麼都沒寫。reasons 是要印給執行的人看的原因，一行一個。"""

    def __init__(self, *reasons: str) -> None:
        super().__init__("\n".join(reasons))
        self.reasons = list(reasons)


def read_json(path: Path) -> object:
    """讀一個 JSON 檔；讀不到或不是合法 JSON 就拒絕執行。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Refused(f"讀不到檔案 {path}：{exc.strerror}") from exc
    except ValueError as exc:
        raise Refused(f"{path} 不是合法的 JSON：{exc}") from exc


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
        raise Refused(*describe_problems(exc, data, id_field=id_field)) from exc


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
            GamesFile, data, id_field="bgg_id", type_codes=repository.list_genre_codes()
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
            repository.replace_game_genres(game_id, game.types)
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
            GamesExport, data, id_field="id", type_codes=repository.list_genre_codes()
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
            repository.replace_game_genres(game.id, game.types)
        repository.set_next_game_id(export.next_id)
    return SyncResult(
        added=len(export.games) - len(same_game_ids),
        updated=len(same_game_ids),
        deleted=deleted,
        next_id=export.next_id,
    )


# --- 讀 reviews.json 的指令 ---


class GameLookup(Protocol):
    """service 查桌遊用到的方法。每款桌遊是一個 dict，至少有 id、bgg_id、name、english_name。"""

    def list_games(self) -> list[dict[str, Any]]: ...

    def find_games_by_bgg_ids(self, bgg_ids: Collection[int]) -> list[dict[str, Any]]: ...


class ReviewStore(Protocol):
    """service 寫心得摘要、心得片段用到的方法。"""

    def transaction(self) -> AbstractContextManager[None]: ...

    def save_review_summary(
        self, game_id: int, summary: str, embedding: Sequence[float], embedding_model: str
    ) -> None: ...

    def delete_review_summary(self, game_id: int) -> None: ...

    def replace_review_excerpts(
        self, game_id: int, excerpts: Sequence[Mapping[str, Any]]
    ) -> None: ...


@dataclass(frozen=True)
class SkippedGame:
    bgg_id: int
    name: str
    reason: str


@dataclass(frozen=True)
class BatchResult:
    """一款一個交易的指令跑完的結果：完成幾款、跳過哪幾款與原因。"""

    done: int
    skipped: list[SkippedGame]

    @property
    def exit_code(self) -> int:
        """0 全部完成；2 部分完成（有款被跳過）。"""
        return 2 if self.skipped else 0


GameReviews = list[tuple[dict[str, Any], list[Review]]]


def _reviews_by_game(
    games: GameLookup, data: object, only_bgg_ids: Collection[int] | None
) -> GameReviews:
    """檢查 reviews.json，回傳這次要處理的桌遊（照 id 排）與各自的心得。

    沒給 only_bgg_ids 就處理資料庫裡全部桌遊，包括 0 篇心得的：它們上一次產生的資料要清掉。
    """
    try:
        reviews = ReviewsFile.model_validate(data).reviews
    except ValidationError as exc:
        problems = describe_problems(exc, data, id_field="bgg_id", items="reviews", unit="篇")
        raise Refused(*problems) from exc

    def missing(bgg_ids: Collection[int]) -> list[int]:
        found = {game["bgg_id"] for game in games.find_games_by_bgg_ids(bgg_ids)}
        return sorted(set(bgg_ids) - found)

    if unknown := missing({review.bgg_id for review in reviews}):
        raise Refused(
            f"reviews.json 有資料庫沒有的 bgg_id：{'、'.join(map(str, unknown))}；"
            "請先匯入或同步桌遊"
        )
    if only_bgg_ids and (unknown := missing(only_bgg_ids)):
        raise Refused(f"--bgg-id 有資料庫沒有的 bgg_id：{'、'.join(map(str, unknown))}")

    targets = games.find_games_by_bgg_ids(only_bgg_ids) if only_bgg_ids else games.list_games()
    return [
        (game, [review for review in reviews if review.bgg_id == game["bgg_id"]])
        for game in targets
    ]


class LLMFailed(Exception):
    """模型這一次沒有給出能用的結果：輸出重試後仍被拒絕，或模型連不上。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def ask_llm[Answer](ask: Callable[[], Answer]) -> Answer:
    """呼叫模型；輸出被拒絕就重試 1 次（spec §7.2 規則 6）。

    重試後仍被拒絕、或模型連不上（SDK 已經重試過）時拋 LLMFailed，由呼叫端跳過這一款。
    其他 LLMError（金鑰錯誤、schema 不符合規定）不攔截，讓整個指令失敗。
    評估題組的評審也用它，但評審連其他 LLMError 都自己攔下（spec §15.6）。
    """
    try:
        try:
            return ask()
        except LLMOutputRejected:
            return ask()
    except LLMOutputRejected as exc:
        raise LLMFailed(f"模型的輸出重試 1 次後仍然不能用：{exc}") from exc
    except LLMUnavailable as exc:
        raise LLMFailed(f"模型連不上：{exc}") from exc


def parse_output[Output: BaseModel](model: type[Output], output: dict[str, Any]) -> Output:
    """確認模型的輸出符合預期的格式；不符合就當作輸出被拒絕，可以重試。"""
    try:
        return model.model_validate(output)
    except ValidationError as exc:
        raise LLMOutputRejected(f"模型的輸出不符合格式：{exc.error_count()} 個問題") from exc


def _for_each_game(
    work: GameReviews, process: Callable[[dict[str, Any], list[Review]], None]
) -> BatchResult:
    """一款一款處理；模型或向量轉換失敗的那一款跳過，其他款照做。"""
    done = 0
    skipped = []
    for game, reviews in work:
        try:
            process(game, reviews)
        except LLMFailed as exc:
            skipped.append(SkippedGame(game["bgg_id"], game["name"], exc.reason))
        except EmbeddingError as exc:
            skipped.append(SkippedGame(game["bgg_id"], game["name"], f"轉成向量失敗：{exc}"))
        else:
            done += 1
    return BatchResult(done=done, skipped=skipped)


def embedding_model_name(config: EmbeddingConfig) -> str:
    """記在每個向量上的模型名稱；用 fake 時記 fake（spec §8.9）。"""
    return "fake" if config.provider == "fake" or config.model is None else config.model


def summarize_reviews(
    games: GameLookup,
    store: ReviewStore,
    data: object,
    *,
    llm: LLMProvider,
    embedding: EmbeddingProvider,
    embedding_config: EmbeddingConfig,
    only_bgg_ids: Collection[int] | None = None,
) -> BatchResult:
    """每款桌遊呼叫 1 次 LLM 讀完全部心得，寫成心得摘要，和向量一起存。"""
    # 讀取也放進交易：讀完就結束交易，不會開著交易等模型回應
    with store.transaction():
        work = _reviews_by_game(games, data, only_bgg_ids)
    embedding_model = embedding_model_name(embedding_config)

    def process(game: dict[str, Any], reviews: list[Review]) -> None:
        if not reviews:
            # 0 篇心得：不呼叫模型，清掉上一次產生的心得摘要
            with store.transaction():
                store.delete_review_summary(game["id"])
            return
        summary = ask_llm(lambda: llm.generate(prompts.summary_prompt(game, reviews)))
        [vector] = embedding.embed([summary])
        with store.transaction():
            store.save_review_summary(game["id"], summary, vector, embedding_model)

    return _for_each_game(work, process)


def build_excerpts(
    games: GameLookup,
    store: ReviewStore,
    data: object,
    *,
    embedding: EmbeddingProvider,
    embedding_config: EmbeddingConfig,
    only_bgg_ids: Collection[int] | None = None,
    limits: ExcerptLimits = DEFAULT_LIMITS,
) -> BatchResult:
    """把每款桌遊的心得切成心得片段，一款的片段一起轉成向量後存。不用 LLM。"""
    with store.transaction():
        work = _reviews_by_game(games, data, only_bgg_ids)
    embedding_model = embedding_model_name(embedding_config)

    def process(game: dict[str, Any], reviews: list[Review]) -> None:
        excerpts = split_reviews(reviews, limits)
        # 0 篇心得：不呼叫 embed，只清掉上一次產生的心得片段
        vectors = embedding.embed([excerpt.text for excerpt in excerpts]) if excerpts else []
        rows = [
            {
                "text": excerpt.text,
                "embedding": vector,
                "embedding_model": embedding_model,
                "source_url": excerpt.source_url,
                "site_name": excerpt.site_name,
                "language": excerpt.language,
            }
            for excerpt, vector in zip(excerpts, vectors, strict=True)
        ]
        with store.transaction():
            store.replace_review_excerpts(game["id"], rows)

    return _for_each_game(work, process)


# --- 標籤詞彙表 ---


@dataclass(frozen=True)
class _NumberedCandidate:
    """編了號的候選詞，記得它來自哪一款桌遊。"""

    id: str
    term: str
    description: str
    source_urls: list[str]
    game_name: str


@dataclass(frozen=True)
class VocabularyDraftResult:
    tags: int
    candidates: int
    skipped: list[SkippedGame]

    @property
    def exit_code(self) -> int:
        """0 全部完成；2 部分完成（有款被跳過）。"""
        return 2 if self.skipped else 0


def _extract_candidates(
    llm: LLMProvider, game: dict[str, Any], reviews: list[Review]
) -> CandidatesOutput:
    def ask() -> CandidatesOutput:
        output = llm.generate_json(
            instructions=prompts.CANDIDATES_INSTRUCTIONS,
            input=prompts.reviews_input(game, reviews),
            schema=prompts.CANDIDATES_SCHEMA,
        )
        return parse_output(CandidatesOutput, output)

    return ask_llm(ask)


def _merge_candidates(llm: LLMProvider, candidates: list[_NumberedCandidate]) -> MergeOutput:
    def ask() -> MergeOutput:
        output = llm.generate_json(
            instructions=prompts.merge_instructions(TAG_VOCABULARY_MAX_TAGS),
            input=prompts.merge_input(candidates),
            schema=prompts.MERGE_SCHEMA,
        )
        return parse_output(MergeOutput, output)

    return ask_llm(ask)


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown 表格。儲存格裡的 | 與換行會弄壞表格，先換掉。"""

    def line(cells: list[str]) -> str:
        return (
            "| " + " | ".join(cell.replace("|", "｜").replace("\n", " ") for cell in cells) + " |"
        )

    return [line(header), line(["---"] * len(header)), *(line(row) for row in rows)]


def _vocabulary_report(
    merged: list[tuple[Any, list[_NumberedCandidate]]],
    discarded: list[tuple[_NumberedCandidate, str]],
    unassigned: list[_NumberedCandidate],
    skipped: list[SkippedGame],
    candidate_count: int,
) -> str:
    """歸納報告（Markdown）：每個標籤的依據、捨棄的候選詞與原因、被跳過的桌遊。"""
    lines = [
        "# 歸納報告",
        "",
        f"{candidate_count} 個候選詞合併成 {len(merged)} 個標籤，依出現的款數由多到少排。",
        "審核時可以刪除、合併、改名稱、改寫定義、改代碼；不能新增這份報告裡找不到依據的標籤。",
        "",
        "## 標籤",
    ]
    for position, (tag, members) in enumerate(merged, start=1):
        game_names = list(dict.fromkeys(member.game_name for member in members))
        lines += [
            "",
            f"### {position}. {tag.name}（`{tag.code}`）",
            "",
            f"- 定義：{tag.definition}",
            f"- 出現在 {len(game_names)} 款：{'、'.join(game_names) or '（沒有對應的候選詞）'}",
            "",
            *_table(
                ["編號", "候選詞", "桌遊", "描述", "依據"],
                [
                    [m.id, m.term, m.game_name, m.description, " ".join(m.source_urls)]
                    for m in members
                ],
            ),
        ]
    lines += ["", "## 捨棄的候選詞", ""]
    lines += (
        _table(
            ["編號", "候選詞", "桌遊", "原因"],
            [[c.id, c.term, c.game_name, reason] for c, reason in discarded],
        )
        if discarded
        else ["沒有。"]
    )
    if unassigned:
        lines += ["", "## 模型沒有歸類的候選詞", ""]
        lines += _table(
            ["編號", "候選詞", "桌遊", "描述"],
            [[c.id, c.term, c.game_name, c.description] for c in unassigned],
        )
    lines += ["", "## 跳過的桌遊", ""]
    lines += (
        [f"- bgg_id {game.bgg_id}「{game.name}」：{game.reason}" for game in skipped]
        if skipped
        else ["沒有。"]
    )
    return "\n".join(lines) + "\n"


def draft_vocabulary(
    games: GameLookup, data: object, *, llm: LLMProvider, out_path: Path, report_path: Path
) -> VocabularyDraftResult:
    """從全部心得歸納出詞彙表草稿與歸納報告。只寫這兩個檔案，不寫資料庫。

    每款有心得的桌遊呼叫 1 次模型擷取候選詞，全部候選詞再呼叫 1 次合併成標籤。
    """
    # 先確認兩個檔案都還不存在，再呼叫模型：不蓋掉立倫編輯過的草稿與當作依據的報告，
    # 也不會跑完模型才發現不能寫
    if existing := [str(path) for path in (out_path, report_path) if path.exists()]:
        raise Refused(*(f"{path} 已經存在；請換一個路徑，或先把它移走" for path in existing))

    candidates: list[_NumberedCandidate] = []
    skipped: list[SkippedGame] = []
    for game, reviews in _reviews_by_game(games, data, None):
        if not reviews:
            continue
        try:
            output = _extract_candidates(llm, game, reviews)
        except LLMFailed as exc:
            skipped.append(SkippedGame(game["bgg_id"], game["name"], exc.reason))
            continue
        for candidate in output.candidates:
            candidates.append(
                _NumberedCandidate(
                    id=f"c{len(candidates) + 1}",
                    term=candidate.term,
                    description=candidate.description,
                    source_urls=candidate.source_urls,
                    game_name=game["name"],
                )
            )
    if not candidates:
        raise Refused(
            "沒有擷取到任何候選詞，兩個檔案都沒有寫",
            *(f"跳過 bgg_id {game.bgg_id}「{game.name}」：{game.reason}" for game in skipped),
        )

    try:
        output = _merge_candidates(llm, candidates)
    except LLMFailed as exc:
        raise Refused(f"合併同義詞失敗，兩個檔案都沒有寫：{exc.reason}") from exc

    by_id = {candidate.id: candidate for candidate in candidates}
    merged = [
        (tag, [by_id[candidate_id] for candidate_id in tag.candidate_ids if candidate_id in by_id])
        for tag in output.tags
    ]
    # 依出現在幾款桌遊由多到少排；一樣多的維持模型給的順序
    merged.sort(key=lambda item: -len({member.game_name for member in item[1]}))
    discarded = [
        (by_id[entry.candidate_id], entry.reason)
        for entry in output.discarded
        if entry.candidate_id in by_id
    ]
    assigned = {member.id for _, members in merged for member in members}
    assigned |= {candidate.id for candidate, _ in discarded}
    unassigned = [candidate for candidate in candidates if candidate.id not in assigned]

    draft = {
        "tags": [
            {"code": tag.code, "name": tag.name, "definition": tag.definition} for tag, _ in merged
        ]
    }
    out_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        _vocabulary_report(merged, discarded, unassigned, skipped, len(candidates)),
        encoding="utf-8",
    )
    return VocabularyDraftResult(tags=len(merged), candidates=len(candidates), skipped=skipped)


class TagStore(Protocol):
    """service 同步標籤詞彙表用到的方法。"""

    def transaction(self) -> AbstractContextManager[None]: ...

    def list_tags(self) -> list[dict[str, str]]: ...

    def add_tag(self, code: str, name: str, definition: str) -> None: ...

    def update_tag(self, code: str, name: str, definition: str) -> None: ...

    def delete_tag(self, code: str) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class VocabularySyncResult:
    # 要印給執行的人看的結果，一行一件事
    lines: list[str]


def sync_vocabulary(store: TagStore, data: object) -> VocabularySyncResult:
    """讓資料表的標籤詞彙表和 tag_vocabulary.json 相同。以代碼認出同一個標籤，整份一個交易。"""
    try:
        wanted = TagVocabularyFile.model_validate(data).tags
    except ValidationError as exc:
        problems = describe_problems(exc, data, id_field="code", items="tags", unit="個")
        raise Refused(*problems) from exc

    lines = []
    with store.transaction():
        current = {tag["code"]: tag for tag in store.list_tags()}
        wanted_codes = {tag.code for tag in wanted}
        # 先刪、再改、最後新增：名稱不能重複，要讓被刪掉或改名的標籤先把名稱讓出來
        for code in sorted(current.keys() - wanted_codes):
            games = store.delete_tag(code)
            names = "、".join(game["name"] for game in games)
            lines.append(
                f"刪掉標籤 {code}（{current[code]['name']}）："
                + (f"{len(games)} 款桌遊少了這個標籤：{names}" if games else "沒有桌遊有這個標籤")
            )
        for tag in wanted:
            old = current.get(tag.code)
            if old and (old["name"], old["definition"]) != (tag.name, tag.definition):
                store.update_tag(tag.code, tag.name, tag.definition)
                lines.append(f"標籤 {tag.code}（{tag.name}）的名稱或定義改了，可以考慮重標")
        added = [tag for tag in wanted if tag.code not in current]
        for tag in added:
            store.add_tag(tag.code, tag.name, tag.definition)
            lines.append(f"新增標籤 {tag.code}（{tag.name}）")
        if added:
            lines.append("有新增的標籤：請重跑上標籤（draft-tags，全部桌遊），並重做人工驗證")
    return VocabularySyncResult(lines=lines or ["標籤詞彙表和檔案相同，沒有變動"])


# --- 每款桌遊的標籤 ---


class TagVocabulary(Protocol):
    """service 讀標籤詞彙表用到的方法。"""

    def list_tags(self) -> list[dict[str, str]]: ...


class GameTagStore(TagVocabulary, Protocol):
    """service 寫每款桌遊的標籤用到的方法。"""

    def transaction(self) -> AbstractContextManager[None]: ...

    def replace_game_tags(self, game_id: int, tags: Sequence[Mapping[str, Any]]) -> None: ...


@dataclass(frozen=True)
class TagDraftResult:
    games: int
    skipped: list[SkippedGame]
    # 提醒，不算失敗：每個標籤被幾款使用、詞彙表可能有問題的標籤（帶 --bgg-id 時沒有這兩種）、
    # 沒有任何標籤的桌遊
    lines: list[str]

    @property
    def exit_code(self) -> int:
        """0 全部完成；2 部分完成（有款被跳過）。"""
        return 2 if self.skipped else 0


@dataclass(frozen=True)
class TagImportResult:
    games: int
    tags: int


def original_path(draft_path: Path) -> Path:
    """標籤草稿的原始檔：檔名加上 .original，例如 tags-draft.original.json。"""
    return draft_path.with_name(f"{draft_path.stem}.original{draft_path.suffix}")


def _tag_problems(output: TagsOutput, codes: set[str], review_urls: set[str]) -> list[str]:
    """上標籤的自動檢查（spec §8.7 第 3 點）；回傳不通過的地方，空的就是通過。"""
    problems = []
    seen: set[str] = set()
    for tag in output.tags:
        if tag.code not in codes:
            problems.append(f"{tag.code} 不在詞彙表裡")
        if tag.code in seen:
            problems.append(f"{tag.code} 重複")
        seen.add(tag.code)
        if not 0 <= tag.confidence <= 1:
            problems.append(f"{tag.code} 的信心分數 {tag.confidence} 不在 0 到 1 之間")
        cited = set(tag.source_urls)
        if not cited:
            problems.append(f"{tag.code} 沒有引用心得")
        elif cited - review_urls:
            problems.append(f"{tag.code} 引用了不是這一款的心得網址")
        if tag.confidence >= TAG_HIGH_CONFIDENCE and len(cited) < TAG_HIGH_CONFIDENCE_MIN_REVIEWS:
            problems.append(
                f"{tag.code} 的信心分數 {tag.confidence} 至少要引用 "
                f"{TAG_HIGH_CONFIDENCE_MIN_REVIEWS} 篇心得"
            )
    return problems


def _judge_tags(
    llm: LLMProvider,
    game: dict[str, Any],
    reviews: list[Review],
    tags: list[dict[str, str]],
) -> TagsOutput:
    codes = [tag["code"] for tag in tags]
    review_urls = {review.source_url for review in reviews}

    def ask() -> TagsOutput:
        output = parse_output(
            TagsOutput,
            llm.generate_json(
                instructions=prompts.tagging_instructions(tags),
                input=prompts.reviews_input(game, reviews),
                schema=prompts.tagging_schema(codes),
            ),
        )
        # 自動檢查不通過，和模型輸出被拒絕一樣處理：重試 1 次，仍不通過就跳過這一款
        if problems := _tag_problems(output, set(codes), review_urls):
            raise LLMOutputRejected("自動檢查不通過：" + "；".join(problems))
        return output

    return ask_llm(ask)


def _tag_usage_lines(
    tags: list[dict[str, str]], entries: list[dict[str, Any]], total_games: int
) -> list[str]:
    """每個標籤被幾款使用；沒有桌遊使用、或太多桌遊都有的標籤，提醒「詞彙表可能有問題」。"""
    lines = []
    for tag in tags:
        count = sum(
            any(judged["code"] == tag["code"] for judged in entry["tags"]) for entry in entries
        )
        line = f"標籤 {tag['code']}（{tag['name']}）：{count} 款使用"
        if count == 0:
            line += "，詞彙表可能有問題（沒有任何桌遊使用）"
        elif total_games and count / total_games >= TAG_USAGE_WARNING_RATIO:
            percent = round(TAG_USAGE_WARNING_RATIO * 100)
            line += f"，詞彙表可能有問題（{percent}% 以上的桌遊都有）"
        lines.append(line)
    return lines


def _untagged_lines(entries: list[dict[str, Any]]) -> list[str]:
    return [
        f"{entry['name']}（bgg_id {entry['bgg_id']}）沒有任何標籤"
        for entry in entries
        if not entry["tags"]
    ]


def draft_tags(
    games: GameLookup,
    vocabulary: TagVocabulary,
    data: object,
    *,
    llm: LLMProvider,
    out_path: Path,
    only_bgg_ids: Collection[int] | None = None,
) -> TagDraftResult:
    """每款桌遊呼叫 1 次模型，照詞彙表選標籤、給信心分數。只寫標籤草稿與原始檔，不寫資料庫。

    被跳過的桌遊不放進草稿，匯入時就不會動它的標籤；0 篇心得的桌遊放進草稿、沒有標籤，
    匯入後它的標籤會清空。
    """
    original = original_path(out_path)
    # 先確認兩個檔案都還不存在，再呼叫模型：不蓋掉立倫刪過標籤的草稿
    if existing := [str(path) for path in (out_path, original) if path.exists()]:
        raise Refused(*(f"{path} 已經存在；請換一個路徑，或先把它移走" for path in existing))
    tags = vocabulary.list_tags()
    if not tags:
        raise Refused("標籤詞彙表是空的；請先執行 sync-vocabulary 同步詞彙表")

    entries = []
    skipped = []
    for game, reviews in _reviews_by_game(games, data, only_bgg_ids):
        judged: list[dict[str, Any]] = []
        if reviews:
            try:
                judged = [tag.model_dump() for tag in _judge_tags(llm, game, reviews, tags).tags]
            except LLMFailed as exc:
                skipped.append(SkippedGame(game["bgg_id"], game["name"], exc.reason))
                continue
        entries.append({"bgg_id": game["bgg_id"], "name": game["name"], "tags": judged})

    content = json.dumps({"games": entries}, ensure_ascii=False, indent=2) + "\n"
    out_path.write_text(content, encoding="utf-8")
    original.write_text(content, encoding="utf-8")
    # 只補跑幾款（--bgg-id）時不統計標籤的使用情況：每個標籤不是 0 款就是全部，
    # 「詞彙表可能有問題」的提醒沒有意義。要檢查詞彙表就跑全部桌遊
    usage = [] if only_bgg_ids else _tag_usage_lines(tags, entries, len(games.list_games()))
    return TagDraftResult(
        games=len(entries), skipped=skipped, lines=usage + _untagged_lines(entries)
    )


def _read_tag_draft(path: Path) -> TagDraftFile:
    data = read_json(path)
    try:
        return TagDraftFile.model_validate(data)
    except ValidationError as exc:
        problems = describe_problems(exc, data, id_field="bgg_id")
        raise Refused(f"{path} 的格式不對", *problems) from exc


def import_tags(games: GameLookup, store: GameTagStore, draft_path: Path) -> TagImportResult:
    """把立倫審核過的標籤草稿寫進資料庫。先檢查整份草稿，有一項不符合就整份拒絕。

    只替換草稿裡有的桌遊，其他款不動；低於門檻的標籤也存；依據的心得網址不存。
    """
    draft = _read_tag_draft(draft_path)
    original = original_path(draft_path)
    if not original.exists():
        raise Refused(
            f"找不到原始檔 {original}；沒有它就不能確認草稿只有刪除標籤，請重跑 draft-tags"
        )
    allowed = {
        game.bgg_id: {tag.code: tag.confidence for tag in game.tags}
        for game in _read_tag_draft(original).games
    }

    problems = []
    codes = {tag["code"] for tag in store.list_tags()}
    if unknown := sorted({tag.code for game in draft.games for tag in game.tags} - codes):
        problems.append(
            f"草稿有詞彙表沒有的代碼：{'、'.join(unknown)}；"
            "產生草稿之後詞彙表改過了，請重跑 draft-tags"
        )
    # 和原始檔比：只能刪除，不能多出桌遊或標籤，也不能改分數
    seen_games: set[int] = set()
    for game in draft.games:
        if game.bgg_id in seen_games:
            problems.append(f"bgg_id {game.bgg_id} 在草稿裡出現兩次")
        seen_games.add(game.bgg_id)
        if game.bgg_id not in allowed:
            problems.append(f"bgg_id {game.bgg_id} 不在原始檔裡：草稿只能刪除，不能新增桌遊")
            continue
        seen_codes: set[str] = set()
        for tag in game.tags:
            original_confidence = allowed[game.bgg_id].get(tag.code)
            if original_confidence is None or tag.code in seen_codes:
                problems.append(f"bgg_id {game.bgg_id} 多了標籤 {tag.code}：草稿只能刪除標籤")
            elif tag.confidence != original_confidence:
                problems.append(
                    f"bgg_id {game.bgg_id} 的 {tag.code} 分數從 {original_confidence} "
                    f"改成 {tag.confidence}：草稿不能改分數"
                )
            seen_codes.add(tag.code)
    found = {game["bgg_id"]: game["id"] for game in games.find_games_by_bgg_ids(sorted(seen_games))}
    if missing := sorted(seen_games - found.keys()):
        problems.append(f"草稿有資料庫沒有的 bgg_id：{'、'.join(map(str, missing))}")
    if problems:
        raise Refused(*problems)

    for game in draft.games:
        with store.transaction():
            store.replace_game_tags(
                found[game.bgg_id],
                [{"code": tag.code, "confidence": tag.confidence} for tag in game.tags],
            )
    return TagImportResult(games=len(draft.games), tags=sum(len(game.tags) for game in draft.games))
