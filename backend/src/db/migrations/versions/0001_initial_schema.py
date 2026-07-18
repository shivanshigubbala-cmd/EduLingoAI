"""initial schema — users, documents, syllabus_topics, sessions, chat_messages, quiz_results

Revision ID: 0001
Revises:
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("storage_path", sa.String, nullable=False),
        sa.Column("mime_type", sa.String, nullable=False),
        sa.Column("status", sa.Enum("pending", "parsed", "failed", name="documentstatus"), nullable=False),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "syllabus_topics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("syllabus_topics.id"), nullable=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("level", sa.Enum("subject", "unit", "topic", "subtopic", name="topiclevel"), nullable=False),
        sa.Column("mastery", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_syllabus_topics_user_id", "syllabus_topics", ["user_id"])
    op.create_index("ix_syllabus_topics_document_id", "syllabus_topics", ["document_id"])

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.Enum("diagnostic", "chat", "quiz", name="sessiontype"), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", name="messagerole"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("topic_reference_id", UUID(as_uuid=True), sa.ForeignKey("syllabus_topics.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.create_table(
        "quiz_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", UUID(as_uuid=True), sa.ForeignKey("syllabus_topics.id"), nullable=False),
        sa.Column("quiz_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("student_answer", sa.Text, nullable=True),
        sa.Column("is_correct", sa.Boolean, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_quiz_results_user_id", "quiz_results", ["user_id"])
    op.create_index("ix_quiz_results_topic_id", "quiz_results", ["topic_id"])
    op.create_index("ix_quiz_results_quiz_id", "quiz_results", ["quiz_id"])


def downgrade():
    op.drop_table("quiz_results")
    op.drop_table("chat_messages")
    op.drop_table("sessions")
    op.drop_table("syllabus_topics")
    op.drop_table("documents")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP TYPE IF EXISTS topiclevel")
    op.execute("DROP TYPE IF EXISTS sessiontype")
    op.execute("DROP TYPE IF EXISTS messagerole")
