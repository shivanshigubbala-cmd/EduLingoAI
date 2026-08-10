"""add quiz feedback idempotency marker

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "quiz_results",
        sa.Column("feedback_applied_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("quiz_results", "feedback_applied_at")
