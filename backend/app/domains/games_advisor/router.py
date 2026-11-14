"""推薦對話 API：POST /api/v1/advisor/messages（spec §13）。

後端不存對話，所以沒有 GET，也沒有列出對話的端點。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.domains.games_advisor.conversation import ConversationService
from app.domains.games_advisor.repository import ReviewRepository, TagRepository
from app.domains.games_advisor.schemas import (
    AdvisorExcerpt,
    AdvisorGame,
    AdvisorRecommendation,
    MessageRequest,
    MessageResponse,
)
from app.domains.games_advisor.search import GameSearch
from app.domains.games_advisor.service import embedding_model_name

router = APIRouter(prefix="/advisor", tags=["games_advisor"])


def get_conversation_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> ConversationService:
    """組出對話 service：LLM 與 embedding 用後端啟動時建立的 provider。測試會覆寫這個依賴。"""
    state = request.app.state
    search = GameSearch(
        games=GameRepository(session),
        tags=TagRepository(session),
        reviews=ReviewRepository(session),
        embedding=state.games_advisor_embedding,
        embedding_model=embedding_model_name(state.games_advisor_embedding_config),
    )
    return ConversationService(search=search, llm=state.llm)


@router.post("/messages", status_code=201, response_model=MessageResponse)
def create_message(
    body: MessageRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageResponse:
    """送出一則訊息，Agent 追問或推薦最多 3 款桌遊。"""
    reply = service.send_message(user, body.content, body.previous_response_id)
    return MessageResponse(
        response_id=reply.response_id,
        reply=reply.reply,
        relaxed_constraint=reply.relaxed_constraint,
        recommendations=[
            AdvisorRecommendation(
                game=AdvisorGame(**card.game),
                reason=card.reason,
                excerpts=[AdvisorExcerpt(**excerpt) for excerpt in card.excerpts],
            )
            for card in reply.recommendations
        ],
    )
