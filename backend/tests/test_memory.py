"""Tests for Postgres-backed rolling chat memory (P5-SHI9)."""
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import ChatMessage, MessageRole, Session, SessionType, User
from src.memory import build_chat_context, summarize_session


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _chat_session(db_session):
    user = User(id=uuid.uuid4(), email="memory@example.com", hashed_password="x")
    session = Session(id=uuid.uuid4(), user_id=user.id, type=SessionType.chat)
    db_session.add_all([user, session])
    db_session.commit()
    return session


def _add_messages(db_session, session, contents):
    base = datetime(2025, 1, 1)
    messages = []
    for index, content in enumerate(contents):
        message = ChatMessage(
            id=uuid.uuid4(), session_id=session.id,
            role=MessageRole.user if index % 2 == 0 else MessageRole.assistant,
            content=content, created_at=base + timedelta(seconds=index),
        )
        db_session.add(message)
        messages.append(message)
    db_session.commit()
    return messages


def _summary_client(*summaries):
    client = MagicMock()
    client.chat.side_effect = [
        {"message": {"content": summary}} for summary in summaries
    ]
    return client


def test_under_threshold_is_untouched(db_session):
    session = _chat_session(db_session)
    _add_messages(db_session, session, ["one", "two"])

    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=MagicMock())

    assert session.summary is None


def test_over_threshold_creates_summary_and_advances_cursor(db_session):
    session = _chat_session(db_session)
    messages = _add_messages(db_session, session, ["one", "two", "three", "four"])
    client = _summary_client("Student asked about momentum.")

    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=client)

    memory = json.loads(session.summary)
    assert memory == {
        "summary": "Student asked about momentum.",
        "summarized_through_message_id": str(messages[1].id),
    }
    assert db_session.query(ChatMessage).filter_by(session_id=session.id).count() == 4


def test_second_call_without_new_messages_is_idempotent(db_session):
    session = _chat_session(db_session)
    _add_messages(db_session, session, ["one", "two", "three"])
    client = _summary_client("First rolling summary")

    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=client)
    first = session.summary
    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=client)

    assert session.summary == first
    assert client.chat.call_count == 1


def test_new_messages_extend_existing_summary(db_session):
    session = _chat_session(db_session)
    initial = _add_messages(db_session, session, ["one", "two", "three"])
    client = _summary_client("First summary", "First summary plus new facts")
    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=client)
    first_memory = json.loads(session.summary)

    later = _add_messages(db_session, session, ["four", "five"])
    # Ensure newly inserted messages sort after the initial tail.
    for index, message in enumerate(later, start=10):
        message.created_at = datetime(2025, 1, 1) + timedelta(seconds=index)
    db_session.commit()
    summarize_session(db_session, session.id, token_budget=50, turns_threshold=2, client=client)

    second_memory = json.loads(session.summary)
    assert second_memory["summary"] == "First summary plus new facts"
    # The former live tail ("two", "three") becomes old history together
    # with new turns, but the message already behind the first cursor is not
    # re-summarized.
    assert second_memory["summarized_through_message_id"] == str(initial[2].id)
    prompt = client.chat.call_args_list[1].kwargs["messages"][1]["content"]
    assert first_memory["summary"] in prompt
    assert "assistant: two" in prompt
    assert "user: one" not in prompt


def test_context_includes_summary_only_post_cursor_and_fits_budget(db_session):
    session = _chat_session(db_session)
    messages = _add_messages(
        db_session, session, ["old one", "old two", "keep this recent", "also keep newest"]
    )
    session.summary = json.dumps(
        {"summary": "important old context", "summarized_through_message_id": str(messages[1].id)}
    )
    db_session.commit()

    context = build_chat_context(db_session, session.id, token_budget=6)

    assert context[0] == {"role": "system", "content": "Conversation summary: important old context"}
    assert [item["content"] for item in context[1:]] == ["also keep newest"]
    assert "old one" not in " ".join(item["content"] for item in context)
    assert sum(len(item["content"].split()) for item in context) <= 9  # includes system-message label


def test_context_does_not_skip_oversized_newest_message_for_older_turn(db_session):
    session = _chat_session(db_session)
    _add_messages(
        db_session,
        session,
        ["small older message", "newest message is too large for this budget"],
    )

    context = build_chat_context(db_session, session.id, token_budget=4)

    assert context == []
