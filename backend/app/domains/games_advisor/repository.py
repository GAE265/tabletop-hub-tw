"""games_advisor 的資料存取。

- 共用桌遊表的 GameRepository 在 app/core/games/repository.py（AGENTS.md §4.2）。
- ReviewRepository：games_advisor 自己的心得摘要與心得片段。
- TagRepository：標籤詞彙表（tag_vocabulary.json 同步出來的副本）與每款桌遊的標籤。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import delete, insert, select, update

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.games_advisor.models import GameTag, ReviewExcerpt, ReviewSummary, Tag


class ReviewRepository(SessionRepository):
    """心得摘要（一款最多一列）與心得片段（一款多列）的寫入。重跑就是覆蓋：先刪再寫。"""

    def save_review_summary(
        self, game_id: int, summary: str, embedding: Sequence[float], embedding_model: str
    ) -> None:
        """寫入一款桌遊的心得摘要、向量與模型名稱；已經有的話取代舊的。"""
        self.delete_review_summary(game_id)
        self.session.execute(
            insert(ReviewSummary).values(
                game_id=game_id,
                summary=summary,
                embedding=list(embedding),
                embedding_model=embedding_model,
            )
        )

    def delete_review_summary(self, game_id: int) -> None:
        self.session.execute(delete(ReviewSummary).where(ReviewSummary.game_id == game_id))

    def replace_review_excerpts(self, game_id: int, excerpts: Sequence[Mapping[str, Any]]) -> None:
        """把一款桌遊的心得片段整組換成 excerpts；給空的清單就是全部刪掉。

        每段要有 text、embedding、embedding_model、source_url、site_name、language。
        """
        self.session.execute(delete(ReviewExcerpt).where(ReviewExcerpt.game_id == game_id))
        if excerpts:
            self.session.execute(
                insert(ReviewExcerpt),
                [{"game_id": game_id, **excerpt} for excerpt in excerpts],
            )


class TagRepository(SessionRepository):
    """標籤詞彙表與每款桌遊的標籤的讀寫。以代碼認出同一個標籤。"""

    def list_tags(self) -> list[dict[str, str]]:
        """全部標籤，照代碼排；每個是 code、name、definition。"""
        tags = self.session.execute(
            select(Tag.code, Tag.name, Tag.definition).order_by(Tag.code)
        ).mappings()
        return [dict(tag) for tag in tags]

    def list_tag_codes(self) -> list[str]:
        return list(self.session.scalars(select(Tag.code).order_by(Tag.code)))

    def add_tag(self, code: str, name: str, definition: str) -> None:
        self.session.execute(insert(Tag).values(code=code, name=name, definition=definition))

    def update_tag(self, code: str, name: str, definition: str) -> None:
        """原地更新名稱與定義；各款桌遊上的這個標籤與信心分數不受影響。"""
        self.session.execute(
            update(Tag).where(Tag.code == code).values(name=name, definition=definition)
        )

    def delete_tag(self, code: str) -> list[dict[str, Any]]:
        """刪掉一個標籤，各款桌遊上的這個標籤跟著刪。

        回傳原本有這個標籤的桌遊，照 id 排；每款是 id、bgg_id、name。
        """
        games = self.session.execute(
            select(Game.id, Game.bgg_id, Game.name)
            .join(GameTag, GameTag.game_id == Game.id)
            .join(Tag, Tag.id == GameTag.tag_id)
            .where(Tag.code == code)
            .order_by(Game.id)
        ).mappings()
        affected = [dict(game) for game in games]
        self.session.execute(delete(Tag).where(Tag.code == code))
        return affected

    def replace_game_tags(self, game_id: int, tags: Sequence[Mapping[str, Any]]) -> None:
        """把一款桌遊的標籤整組換成 tags；每個是 code 與 confidence。低於門檻的也存。"""
        self.session.execute(delete(GameTag).where(GameTag.game_id == game_id))
        if not tags:
            return
        codes = {tag["code"] for tag in tags}
        tag_ids = dict(
            self.session.execute(select(Tag.code, Tag.id).where(Tag.code.in_(codes))).all()
        )
        if unknown := sorted(codes - set(tag_ids)):
            raise ValueError(f"詞彙表沒有這些代碼：{'、'.join(unknown)}")
        self.session.execute(
            insert(GameTag),
            [
                {
                    "game_id": game_id,
                    "tag_id": tag_ids[tag["code"]],
                    "confidence": tag["confidence"],
                }
                for tag in tags
            ],
        )
