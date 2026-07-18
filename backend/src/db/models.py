"""
ORM models for the Student AI Tool (EduLingoAI) core schema.

Covers the six tables required by P0-SRE2:
  users, documents, syllabus_topics, sessions, chat_messages, quiz_results

Design notes:
- syllabus_topics is self-referential (parent_id) so a single flat table can
  represent the frozen topic-tree shape agreed in P0-TEAM2:
  subject -> unit -> topic -> subtopic, each row carrying a `level` and a
  0-1 `mastery` score. This is what P2-SHI4/P2-SHI5 write into and what
  P3-SHI6 updates.
- sessions is generic (type: diagnostic | chat | quiz) rather than one table
  per feature, since P5-SHI9 (memory summarization) and P5-SHI10 (chat
  history) both need to enumerate "past sessions" regardless of type.
- quiz_results stores one row per graded question rather than one row per
  quiz, so P6-SHI11's per-topic breakdown is a simple GROUP BY topic_id.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Float, ForeignKey, DateTime, Enum, Text, Integer
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base


def gen_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    syllabus_topics = relationship("SyllabusTopic", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="owner", cascade="all, delete-orphan")
    quiz_results = relationship("QuizResult", back_populates="owner", cascade="all, delete-orphan")


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    parsed = "parsed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.pending, nullable=False)
    ocr_confidence = Column(Float, nullable=True)  # set for handwritten uploads, P2-SHR4
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="documents")
    syllabus_topics = relationship("SyllabusTopic", back_populates="document", cascade="all, delete-orphan")


class TopicLevel(str, enum.Enum):
    subject = "subject"
    unit = "unit"
    topic = "topic"
    subtopic = "subtopic"


class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("syllabus_topics.id"), nullable=True)

    name = Column(String, nullable=False)
    level = Column(Enum(TopicLevel), nullable=False)
    mastery = Column(Float, nullable=True)  # 0-1, set after diagnostic (P3-SHI6)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="syllabus_topics")
    document = relationship("Document", back_populates="syllabus_topics")
    children = relationship("SyllabusTopic", backref="parent", remote_side=[id])


class SessionType(str, enum.Enum):
    diagnostic = "diagnostic"
    chat = "chat"
    quiz = "quiz"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(SessionType), nullable=False)
    summary = Column(Text, nullable=True)  # compressed history, P5-SHI9
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="sessions")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    topic_reference_id = Column(UUID(as_uuid=True), ForeignKey("syllabus_topics.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="chat_messages")
    topic_reference = relationship("SyllabusTopic")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("syllabus_topics.id"), nullable=False, index=True)
    quiz_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # groups rows from one quiz attempt
    question = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)  # for short-answer LLM rubric grading, P6-SHR9
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="quiz_results")
    topic = relationship("SyllabusTopic")
