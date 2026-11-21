"""規則影片的非同步工作：rules_qa_video_jobs

產生草稿、產生影片、修改都可能超過 30 秒，做成工作由後端的背景執行緒處理
（openspec/changes/add-rules-video-mobile，design.md D2）。

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "rules_qa_video_jobs"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="工作編號（UUID）",
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("rules_qa_video_projects.id"),
            nullable=False,
            comment="屬於哪一個影片專案",
        ),
        sa.Column(
            "kind",
            sa.Text(),
            nullable=False,
            comment=(
                "工作種類：draft＝產生草稿（讀規則書頁面，由 AI 產生段資料與素材清單，"
                "並跑涵蓋檢查，例如《血與刃》步驟三的草稿）；render＝產生影片（旁白、段影片、"
                "疊進度條、混音）；revise＝用一句話修改（例如「情況二的紅框改成金框」）"
            ),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="queued",
            comment=(
                "狀態：queued＝已建立、等背景執行緒處理；running＝處理中，進度會更新；"
                "succeeded＝完成，結果在 result；failed＝失敗，原因在 error。"
                "succeeded、failed 不再改變，重試要建立新工作"
            ),
        ),
        sa.Column(
            "progress",
            sa.Double(),
            nullable=False,
            server_default="0",
            comment="進度 0 到 1；完成時為 1",
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=True,
            comment="現在在做什麼，給店員看，例如「段影片 2／3」；空值代表還沒有回報",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="失敗原因與下一步，給店員看；空值代表沒有失敗",
        ),
        sa.Column(
            "error_detail",
            sa.Text(),
            nullable=True,
            comment=(
                "失敗時的例外類型與訊息（最多 2000 字），給開發者看、不在 API 回傳；"
                "空值代表沒有未預期的例外"
            ),
        ),
        sa.Column(
            "result",
            postgresql.JSONB(),
            nullable=True,
            comment="完成時的結果；空值代表還沒完成或失敗",
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="建立工作的使用者",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="建立工作的時間；背景執行緒依此先建立的先做",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="開始處理的時間；空值代表還在等待。超過 30 分鐘仍在處理中視為逾時",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="完成或失敗的時間；空值代表還沒結束",
        ),
        sa.CheckConstraint(
            "kind IN ('draft', 'render', 'revise')", name="ck_rules_qa_video_jobs_kind"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_rules_qa_video_jobs_status",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 1", name="ck_rules_qa_video_jobs_progress"
        ),
        comment="規則影片的非同步工作：產生草稿、產生影片、修改，由後端的背景執行緒依序處理",
    )
    # 同一個專案同時只能有一個等待中或處理中的工作（409 RULES_VIDEO_JOB_RUNNING 由此保證）
    op.create_index(
        "ux_rules_qa_video_jobs_active",
        TABLE,
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index("ix_rules_qa_video_jobs_project_created", TABLE, ["project_id", "created_at"])
    # 背景執行緒取下一個等待中的工作
    op.create_index(
        "ix_rules_qa_video_jobs_queued",
        TABLE,
        ["created_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    op.drop_index("ix_rules_qa_video_jobs_queued", table_name=TABLE)
    op.drop_index("ix_rules_qa_video_jobs_project_created", table_name=TABLE)
    op.drop_index("ux_rules_qa_video_jobs_active", table_name=TABLE)
    op.drop_table(TABLE)
