"""scope document content hash per user

Revision ID: bed55f5e8630
Revises: b9fc260a9146
Create Date: 2026-09-27 13:52:24.977805
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'bed55f5e8630'
down_revision: str | None = 'b9fc260a9146'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.drop_index(
        "ix_documents_content_hash",
        table_name="documents",
    )

    op.create_index(
        "ix_documents_user_content_hash",
        "documents",
        ["user_id", "content_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(
        "ix_documents_user_content_hash",
        table_name="documents",
    )

    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=True,
    )