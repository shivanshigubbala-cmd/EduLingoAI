"""add feedback suggestions and schedule milestones

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", UUID(as_uuid=True), sa.ForeignKey("syllabus_topics.id"), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_feedback_suggestions_user_id", "feedback_suggestions", ["user_id"])
    op.create_index("ix_feedback_suggestions_active", "feedback_suggestions", ["active"])
    op.create_table(
        "schedule_milestones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("schedule_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "schedule_id", "day_index", name="uq_schedule_milestone_day"),
    )
    op.create_index("ix_schedule_milestones_user_id", "schedule_milestones", ["user_id"])
    op.create_index("ix_schedule_milestones_schedule_id", "schedule_milestones", ["schedule_id"])


def downgrade():
    op.drop_index("ix_schedule_milestones_schedule_id", table_name="schedule_milestones")
    op.drop_index("ix_schedule_milestones_user_id", table_name="schedule_milestones")
    op.drop_table("schedule_milestones")
    op.drop_index("ix_feedback_suggestions_active", table_name="feedback_suggestions")
    op.drop_index("ix_feedback_suggestions_user_id", table_name="feedback_suggestions")
    op.drop_table("feedback_suggestions")
