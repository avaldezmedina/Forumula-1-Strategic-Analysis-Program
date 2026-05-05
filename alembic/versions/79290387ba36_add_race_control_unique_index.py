"""add_race_control_unique_index

Revision ID: 79290387ba36
Revises: f43b863a5875
Create Date: 2026-05-05 06:01:59.941833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79290387ba36'
down_revision: Union[str, Sequence[str], None] = 'f43b863a5875'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove existing duplicate race-control rows before adding the unique index.
    # Keep the lowest id for each duplicate event group.
    op.execute(
        """
        DELETE FROM race_control
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            session_key,
                            year,
                            driver_number,
                            category,
                            message,
                            flag,
                            scope,
                            sector,
                            lap_number,
                            occurred_at
                        ORDER BY id
                    ) AS row_num
                FROM race_control
            ) duplicates
            WHERE duplicates.row_num > 1
        );
        """
    )

    # Postgres 15 supports NULLS NOT DISTINCT on unique indexes.
    # This is important because several race_control identity fields are nullable.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_race_control_event
        ON race_control (
            session_key,
            year,
            driver_number,
            category,
            message,
            flag,
            scope,
            sector,
            lap_number,
            occurred_at
        )
        NULLS NOT DISTINCT;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_race_control_event;")