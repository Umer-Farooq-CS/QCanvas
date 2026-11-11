"""Add admin access request timestamp.

Revision ID: d9f4b1a2c6e8
Revises: b4672b17caf0
Create Date: 2026-11-11 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9f4b1a2c6e8"
down_revision: Union[str, Sequence[str], None] = "b4672b17caf0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("admin_access_requested_at", sa.TIMESTAMP(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "admin_access_requested_at")
