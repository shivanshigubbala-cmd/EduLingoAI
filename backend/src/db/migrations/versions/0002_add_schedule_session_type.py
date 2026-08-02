"""add schedule session type

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE sessiontype ADD VALUE IF NOT EXISTS 'schedule'")


def downgrade():
    op.execute("ALTER TYPE sessiontype RENAME TO sessiontype_old")
    op.execute("CREATE TYPE sessiontype AS ENUM ('diagnostic', 'chat', 'quiz')")
    op.execute(
        "ALTER TABLE sessions ALTER COLUMN type TYPE sessiontype "
        "USING type::text::sessiontype"
    )
    op.execute("DROP TYPE sessiontype_old")
