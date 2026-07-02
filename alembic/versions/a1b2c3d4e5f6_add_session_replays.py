"""add_session_replays

Revision ID: a1b2c3d4e5f6
Revises: 79290387ba36
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "79290387ba36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_replays",
        sa.Column("session_key", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("frame_interval_ms", sa.Integer(), nullable=False),
        sa.Column("bundle_path", sa.String(length=512), nullable=True),
        sa.Column("built_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_key"], ["sessions.session_key"]),
        sa.PrimaryKeyConstraint("session_key"),
    )
    op.create_table(
        "circuit_tracks",
        sa.Column("circuit_key", sa.Integer(), nullable=False),
        sa.Column("polyline", sa.JSON(), nullable=False),
        sa.Column("source_session_key", sa.Integer(), nullable=True),
        sa.Column("computed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_session_key"], ["sessions.session_key"]),
        sa.PrimaryKeyConstraint("circuit_key"),
    )


def downgrade() -> None:
    op.drop_table("circuit_tracks")
    op.drop_table("session_replays")
