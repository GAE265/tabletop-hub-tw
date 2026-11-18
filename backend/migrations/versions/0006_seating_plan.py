"""seating plan: seating_tables 擴充座位圖座標欄位

Revision ID: 0006
Revises: 0003
Create Date: 2026-11-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0003"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seating_tables",
        sa.Column(
            "floor",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
            comment="樓層：1=1F，-1=B1",
        ),
    )
    op.add_column(
        "seating_tables",
        sa.Column(
            "x",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="桌子在座位圖畫布上的 X 座標（像素）",
        ),
    )
    op.add_column(
        "seating_tables",
        sa.Column(
            "y",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="桌子在座位圖畫布上的 Y 座標（像素）",
        ),
    )
    op.add_column(
        "seating_tables",
        sa.Column(
            "width",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
            comment="桌子在座位圖上的寬度（像素）",
        ),
    )
    op.add_column(
        "seating_tables",
        sa.Column(
            "height",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
            comment="桌子在座位圖上的高度（像素）",
        ),
    )
    op.add_column(
        "seating_tables",
        sa.Column(
            "shape",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'rectangle'"),
            comment="桌子形狀，目前固定為 rectangle",
        ),
    )


def downgrade() -> None:
    op.drop_column("seating_tables", "shape")
    op.drop_column("seating_tables", "height")
    op.drop_column("seating_tables", "width")
    op.drop_column("seating_tables", "y")
    op.drop_column("seating_tables", "x")
    op.drop_column("seating_tables", "floor")
