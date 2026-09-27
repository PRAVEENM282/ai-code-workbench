"""Allow arbitrary validated language labels in request history."""

import sqlalchemy as sa
from alembic import op

revision = "0002_open_language_names"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "request_history",
        "language",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "request_history",
        "language",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
