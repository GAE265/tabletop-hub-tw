"""rules_qa service 的單元測試：FakeRulesQaRepository、FakeEmbeddingProvider、FakeLLMProvider，
不連資料庫、不需要金鑰（AGENTS.md 7.5、7.6）。

情境對應 openspec/specs/rules-qa/spec.md。
"""

import uuid
from typing import Any

import pytest

from app.core.auth import CurrentUser
from app.core.errors import AppError, PermissionDenied
from app.integrations.embedding import EmbeddingUnavailable, FakeEmbeddingProvider
from app.integrations.llm.errors import LLMConversationNotFound, LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider, FakeResponse

PLAYER = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")
STAFF = CurrentUser(
    id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    role="shop_staff",
    shop_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
)
ADMIN = CurrentUser(id=uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), role="admin")

ROSE = 1  # 有影片、有規則書
MARCO = 3  # 只有規則書
AVALON = 4  # 只有影片
EMPTY = 9  # 沒有教材
VIDEO_URL = "https://youtu.be/XE-Sw_FtFFs"
QUESTION = "一個回合可以做什麼？"

# 用 3 維的固定向量控制檢索順序：問題最接近第 5 頁，其次第 3 頁
Q_VECTOR = [1.0, 0.0, 0.0]
PAGE5 = [1.0, 0.0, 0.0]
PAGE5_B = [0.95, 0.05, 0.0]
PAGE3 = [0.8, 0.2, 0.0]
FAR = [0.0, 0.0, 1.0]


def answer(text: str = "每個回合抽兩張牌。", answerable: bool = True, ids: list[int] | None = None):
    return FakeResponse(
        output={"answer": text, "answerable": answerable, "citation_ids": ids or []}
    )


@pytest.fixture
def repo():
    from tests.rules_qa.fakes import FakeRulesQaRepository

    fake = FakeRulesQaRepository()
    for game_id, name in [
        (ROSE, "血與刃的白薔薇"),
        (MARCO, "馬可波羅"),
        (AVALON, "阿瓦隆"),
        (EMPTY, "沒教材的遊戲"),
    ]:
        fake.add_game(game_id, name)
    fake.add_chunk(ROSE, 5, "每個回合可以抽兩張牌。", PAGE5)
    fake.add_chunk(ROSE, 5, "也可以改成打出一張牌。", PAGE5_B)
    fake.add_chunk(ROSE, 3, "遊戲開始時每人拿五張牌。", PAGE3)
    fake.add_chunk(ROSE, 9, "結束時計算分數。", FAR)
    fake.add_chunk(MARCO, 2, "馬可波羅的回合流程。", PAGE5)
    return fake


@pytest.fixture
def embedding() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dim=3, vectors={QUESTION: Q_VECTOR, "那兩個人玩呢？": Q_VECTOR})


def make_service(repo, embedding, llm: FakeLLMProvider):
    from app.domains.rules_qa.service import RulesQaService

    return RulesQaService(repo, embedding=embedding, embedding_model="fake", llm=llm)


def video_in(**overrides: Any):
    from app.domains.rules_qa.schemas import VideoRequest

    return VideoRequest(**{"video_url": VIDEO_URL, "title": "血與刃的白薔薇 規則影片", **overrides})


def message_in(content: str = QUESTION, previous: str | None = None):
    from app.domains.rules_qa.schemas import MessageRequest

    return MessageRequest(content=content, previous_response_id=previous)


def assert_app_error(exc_info: pytest.ExceptionInfo[AppError], status: int, code: str) -> None:
    assert exc_info.value.status_code == status
    assert exc_info.value.code == code


@pytest.fixture
def with_video(repo, embedding):
    make_service(repo, embedding, FakeLLMProvider()).set_video(ADMIN, ROSE, video_in())
    make_service(repo, embedding, FakeLLMProvider()).set_video(
        ADMIN, AVALON, video_in(video_url="https://www.youtube.com/watch?v=abcdefghijk")
    )


# --- 規則教學清單 ---


def test_list_lessons(repo, embedding, with_video):
    lessons = make_service(repo, embedding, FakeLLMProvider()).list_lessons(PLAYER)
    # 依遊戲名稱排序（由 service 排，不受資料庫定序影響）；沒有教材的遊戲不列出
    assert [
        (item.game_id, item.game_name, item.has_video, item.has_rulebook) for item in lessons.items
    ] == sorted(
        [
            (ROSE, "血與刃的白薔薇", True, True),
            (AVALON, "阿瓦隆", True, False),
            (MARCO, "馬可波羅", False, True),
        ],
        key=lambda row: row[1],
    )


def test_list_lessons_empty(embedding):
    from tests.rules_qa.fakes import FakeRulesQaRepository

    lessons = make_service(FakeRulesQaRepository(), embedding, FakeLLMProvider()).list_lessons(
        PLAYER
    )
    assert lessons.items == []


# --- 教學內容 ---


def test_get_lesson_with_video(repo, embedding, with_video):
    lesson = make_service(repo, embedding, FakeLLMProvider()).get_lesson(PLAYER, ROSE)
    assert lesson.game_name == "血與刃的白薔薇"
    assert lesson.video is not None
    assert (lesson.video.source, lesson.video.youtube_id) == ("youtube", "XE-Sw_FtFFs")
    assert lesson.video.title == "血與刃的白薔薇 規則影片"
    assert lesson.has_rulebook is True
    assert lesson.suggested_questions


def test_get_lesson_without_video(repo, embedding):
    lesson = make_service(repo, embedding, FakeLLMProvider()).get_lesson(PLAYER, MARCO)
    assert lesson.video is None
    assert lesson.has_rulebook is True


def test_get_lesson_game_not_found(repo, embedding):
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).get_lesson(PLAYER, 999)
    assert_app_error(exc_info, 404, "GAME_NOT_FOUND")


def test_get_lesson_without_materials(repo, embedding):
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).get_lesson(PLAYER, EMPTY)
    assert_app_error(exc_info, 404, "RULES_LESSON_NOT_FOUND")


# --- 設定教學影片 ---


@pytest.mark.parametrize("user", [STAFF, ADMIN])
def test_set_video(repo, embedding, user):
    video = make_service(repo, embedding, FakeLLMProvider()).set_video(user, MARCO, video_in())
    assert (video.source, video.youtube_id, video.video_url) == (
        "youtube",
        "XE-Sw_FtFFs",
        VIDEO_URL,
    )
    assert repo.get_video(MARCO) is not None


def test_set_video_replaces_existing(repo, embedding, with_video):
    service = make_service(repo, embedding, FakeLLMProvider())
    service.set_video(ADMIN, ROSE, video_in(video_url="https://youtu.be/abcdefghijk", title="新版"))
    lesson = service.get_lesson(PLAYER, ROSE)
    assert (lesson.video.youtube_id, lesson.video.title) == ("abcdefghijk", "新版")


def test_set_video_short_url_with_query(repo, embedding):
    service = make_service(repo, embedding, FakeLLMProvider())
    video = service.set_video(ADMIN, MARCO, video_in(video_url=VIDEO_URL + "?si=xyz"))
    assert video.youtube_id == "XE-Sw_FtFFs"


def test_set_video_rejects_non_youtube(repo, embedding):
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).set_video(
            ADMIN, MARCO, video_in(video_url="https://vimeo.com/123")
        )
    assert_app_error(exc_info, 422, "RULES_QA_INVALID_VIDEO_URL")
    assert repo.get_video(MARCO) is None


def test_player_cannot_set_video(repo, embedding):
    with pytest.raises(PermissionDenied):
        make_service(repo, embedding, FakeLLMProvider()).set_video(PLAYER, MARCO, video_in())
    assert repo.get_video(MARCO) is None


def test_set_video_game_not_found(repo, embedding):
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).set_video(ADMIN, 999, video_in())
    assert_app_error(exc_info, 404, "GAME_NOT_FOUND")


# --- 建立規則書索引 ---


def test_build_index_replaces_manual_chunks(repo):
    from app.domains.rules_qa.service import build_index

    embedding = FakeEmbeddingProvider(dim=3)
    pages = {MARCO: [(1, "第一頁。"), (2, ""), (3, "第三頁。")]}
    count = build_index(repo, pages.get, embedding, "fake", MARCO)
    assert count == 2
    marco = [c for c in repo.chunks if c.game_id == MARCO]
    assert sorted(c.page for c in marco) == [1, 3]
    assert all(len(c.embedding) == 3 and c.embedding_model == "fake" for c in marco)
    # 其他遊戲的段落不受影響
    assert len([c for c in repo.chunks if c.game_id == ROSE]) == 4


def test_build_index_twice_gives_same_result(repo):
    from app.domains.rules_qa.service import build_index

    embedding = FakeEmbeddingProvider(dim=3)
    pages = {MARCO: [(1, "第一頁。")]}
    build_index(repo, pages.get, embedding, "fake", MARCO)
    build_index(repo, pages.get, embedding, "fake", MARCO)
    assert len([c for c in repo.chunks if c.game_id == MARCO]) == 1


def test_build_index_without_pages(repo):
    from app.domains.rules_qa.service import NoRulebookPages, build_index

    with pytest.raises(NoRulebookPages):
        build_index(repo, {}.get, FakeEmbeddingProvider(dim=3), "fake", MARCO)
    # 失敗時不動原本的段落
    assert len([c for c in repo.chunks if c.game_id == MARCO]) == 1


# --- 規則問答 ---


def test_answer_with_page_citation(repo, embedding):
    llm = FakeLLMProvider(responses=[answer(ids=[1])])
    reply = make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert reply.answerable is True
    assert reply.answer == "每個回合抽兩張牌。"
    assert [c.page for c in reply.citations] == [5]
    assert reply.response_id == "fake_resp_1"
    call = llm.calls[0].kwargs
    assert call["previous_response_id"] is None
    assert call["allow_tool_calls"] is False
    assert QUESTION in call["input"]
    assert "每個回合可以抽兩張牌。" in call["input"]


def test_citations_same_page_merged_and_sorted(repo, embedding):
    llm = FakeLLMProvider(responses=[answer(ids=[3, 1, 2])])
    reply = make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert [c.page for c in reply.citations] == [3, 5]


def test_follow_up_passes_previous_response_and_searches_again(repo, embedding):
    llm = FakeLLMProvider(responses=[answer(ids=[1]), answer(ids=[1])])
    service = make_service(repo, embedding, llm)
    first = service.send_message(PLAYER, ROSE, message_in())
    service.send_message(PLAYER, ROSE, message_in("那兩個人玩呢？", previous=first.response_id))
    assert llm.calls[1].kwargs["previous_response_id"] == first.response_id
    assert embedding.calls[-1] == ["那兩個人玩呢？"]
    assert len(repo.searches) == 2


def test_not_answerable_has_no_citations(repo, embedding):
    llm = FakeLLMProvider(responses=[answer("規則書中找不到。", answerable=False, ids=[1])])
    reply = make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert reply.answerable is False
    assert reply.citations == []


def test_only_this_games_chunks_are_searched(repo, embedding):
    llm = FakeLLMProvider(responses=[answer(ids=[1])])
    make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert repo.searches[0][0] == ROSE
    assert "馬可波羅的回合流程。" not in llm.calls[0].kwargs["input"]


def test_citations_outside_search_results_are_dropped(repo, embedding):
    llm = FakeLLMProvider(responses=[answer(ids=[1, 99, 0, -1])])
    reply = make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert [c.page for c in reply.citations] == [5]


def test_wording_rewritten_once(repo, embedding):
    llm = FakeLLMProvider(
        responses=[answer("每次輪到你時抽兩張牌。", ids=[1]), answer("每個回合抽兩張牌。", ids=[1])]
    )
    reply = make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert reply.answer == "每個回合抽兩張牌。"
    assert len(llm.calls) == 2
    assert llm.calls[1].kwargs["previous_response_id"] == "fake_resp_1"
    assert "次" in llm.calls[1].kwargs["input"]
    assert reply.response_id == "fake_resp_2"


def test_wording_still_wrong_after_rewrite(repo, embedding):
    llm = FakeLLMProvider(
        responses=[answer("每次抽牌。", ids=[1]), answer("一次抽兩張。", ids=[1])]
    )
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert_app_error(exc_info, 503, "RULES_QA_OUTPUT_REJECTED")


def test_no_chunks_is_409_without_calling_llm(repo, embedding):
    llm = FakeLLMProvider(responses=[])
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, llm).send_message(PLAYER, AVALON, message_in())
    assert_app_error(exc_info, 409, "RULES_QA_NOT_READY")
    assert llm.calls == []


def test_message_game_not_found(repo, embedding):
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).send_message(PLAYER, 999, message_in())
    assert_app_error(exc_info, 404, "GAME_NOT_FOUND")


@pytest.mark.parametrize(
    "error", [LLMUnavailable("連不上"), EmbeddingUnavailable("連不上")], ids=["llm", "embedding"]
)
def test_service_unavailable_is_503(repo, error):
    if isinstance(error, EmbeddingUnavailable):
        embedding = FakeEmbeddingProvider(dim=3, error=error)
        llm = FakeLLMProvider(responses=[])
    else:
        embedding = FakeEmbeddingProvider(dim=3, vectors={QUESTION: Q_VECTOR})
        llm = FakeLLMProvider(responses=[error])
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, llm).send_message(PLAYER, ROSE, message_in())
    assert_app_error(exc_info, 503, "RULES_QA_UNAVAILABLE")


def test_expired_conversation_is_404(repo, embedding):
    llm = FakeLLMProvider(responses=[LLMConversationNotFound("找不到")])
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, llm).send_message(
            PLAYER, ROSE, message_in(previous="resp_old")
        )
    assert_app_error(exc_info, 404, "RULES_QA_CONVERSATION_NOT_FOUND")


@pytest.mark.parametrize("user", [PLAYER, STAFF, ADMIN])
def test_every_role_can_ask(repo, embedding, user):
    llm = FakeLLMProvider(responses=[answer(ids=[1])])
    assert make_service(repo, embedding, llm).send_message(user, ROSE, message_in()).answer


# --- index_page：規則書單頁匯入後立即重建該頁索引 ---

# 兩段各 600 字，合併檢查會超過上限，因此切出 2 個段落（chunking.split_pages）
LONG_A = "甲。" * 300
LONG_B = "乙。" * 300


def test_index_page_returns_chunk_count_and_stores_them(repo, embedding):
    count = make_service(repo, embedding, FakeLLMProvider()).index_page(
        ROSE, 7, f"{LONG_A}\n\n{LONG_B}"
    )
    assert count == 2
    stored = [c for c in repo.chunks if (c.game_id, c.page) == (ROSE, 7)]
    assert [c.content for c in stored] == [LONG_A, LONG_B]
    assert {c.embedding_model for c in stored} == {"fake"}
    assert all(len(c.embedding) == 3 for c in stored)


def test_index_page_replaces_only_that_page(repo, embedding):
    make_service(repo, embedding, FakeLLMProvider()).index_page(ROSE, 5, "新的第 5 頁內容。")
    stored = {(c.game_id, c.page, c.content) for c in repo.chunks}
    assert (ROSE, 5, "新的第 5 頁內容。") in stored
    assert (ROSE, 5, "每個回合可以抽兩張牌。") not in stored
    assert (ROSE, 5, "也可以改成打出一張牌。") not in stored
    assert (ROSE, 3, "遊戲開始時每人拿五張牌。") in stored
    assert (ROSE, 9, "結束時計算分數。") in stored
    assert (MARCO, 2, "馬可波羅的回合流程。") in stored


def test_index_page_twice_keeps_only_latest(repo, embedding):
    service = make_service(repo, embedding, FakeLLMProvider())
    service.index_page(MARCO, 8, "第一版")
    service.index_page(MARCO, 8, "第二版")
    stored = [c.content for c in repo.chunks if (c.game_id, c.page) == (MARCO, 8)]
    assert stored == ["第二版"]


def test_index_page_blank_page_clears_chunks_without_embedding(repo, embedding):
    count = make_service(repo, embedding, FakeLLMProvider()).index_page(ROSE, 5, "")
    assert count == 0
    assert embedding.calls == []
    assert [c for c in repo.chunks if (c.game_id, c.page) == (ROSE, 5)] == []
    assert any(c.game_id == ROSE for c in repo.chunks)


def test_index_page_embedding_failure_is_503_and_keeps_chunks(repo):
    before = [(c.game_id, c.page, c.content) for c in repo.chunks]
    embedding = FakeEmbeddingProvider(dim=3, error=EmbeddingUnavailable("連不上"))
    with pytest.raises(AppError) as exc_info:
        make_service(repo, embedding, FakeLLMProvider()).index_page(ROSE, 5, "新的第 5 頁內容。")
    assert_app_error(exc_info, 503, "RULES_QA_UNAVAILABLE")
    assert [(c.game_id, c.page, c.content) for c in repo.chunks] == before
