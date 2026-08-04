"""Tests for backend/src/rag/chat_store.py and retrieval.py — P5-SRE10."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import ChatMessage, MessageRole, Session as SessionModel, SessionType, User
from src.rag.chat_store import embed_chat_turn, search_similar_chat_turns
from src.rag.retrieval import retrieve_context


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestEmbedChatTurn:
    def test_embeds_existing_message(self, db_session):
        user = User(id=uuid.uuid4(), email="s@example.com", hashed_password="x", name="S")
        chat_session = SessionModel(id=uuid.uuid4(), user_id=user.id, type=SessionType.chat)
        message = ChatMessage(
            id=uuid.uuid4(),
            session_id=chat_session.id,
            role=MessageRole.user,
            content="What is mitosis?",
        )
        db_session.add_all([user, chat_session, message])
        db_session.commit()

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value.collections = []

        with patch("src.rag.chat_store.embed_text") as mock_embed:
            mock_embed.return_value = [0.1] * 768
            embed_chat_turn(db_session, user.id, message.id, client=mock_qdrant)

        mock_qdrant.upsert.assert_called_once()
        call_kwargs = mock_qdrant.upsert.call_args.kwargs
        point = call_kwargs["points"][0]
        assert point.payload["text"] == "What is mitosis?"
        assert point.payload["role"] == "user"

    def test_raises_on_missing_message(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            embed_chat_turn(db_session, uuid.uuid4(), uuid.uuid4(), client=MagicMock())

    def test_raises_on_empty_content(self, db_session):
        user = User(id=uuid.uuid4(), email="s2@example.com", hashed_password="x", name="S2")
        chat_session = SessionModel(id=uuid.uuid4(), user_id=user.id, type=SessionType.chat)
        message = ChatMessage(
            id=uuid.uuid4(), session_id=chat_session.id, role=MessageRole.user, content="   ",
        )
        db_session.add_all([user, chat_session, message])
        db_session.commit()

        with pytest.raises(ValueError, match="empty chat message"):
            embed_chat_turn(db_session, user.id, message.id, client=MagicMock())


class TestSearchSimilarChatTurns:
    def test_returns_formatted_results(self):
        mock_qdrant = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "chat_turns"
        mock_qdrant.get_collections.return_value.collections = [mock_collection]

        mock_point = MagicMock()
        mock_point.payload = {
            "message_id": "abc",
            "session_id": "def",
            "role": "assistant",
            "text": "Mitosis has four phases.",
        }
        mock_point.score = 0.82
        mock_qdrant.query_points.return_value.points = [mock_point]

        with patch("src.rag.chat_store.embed_text") as mock_embed:
            mock_embed.return_value = [0.1] * 768
            results = search_similar_chat_turns(uuid.uuid4(), "what is mitosis", client=mock_qdrant)

        assert len(results) == 1
        assert results[0]["text"] == "Mitosis has four phases."
        assert results[0]["score"] == 0.82


class TestRetrieveContext:
    def test_combines_syllabus_and_chat_matches(self):
        with patch("src.rag.retrieval.search_similar_chunks") as mock_syllabus, \
             patch("src.rag.retrieval.search_similar_chat_turns") as mock_chat:
            mock_syllabus.return_value = [{"topic_name": "Mitosis", "score": 0.9}]
            mock_chat.return_value = [{"text": "past turn", "score": 0.7}]

            result = retrieve_context(uuid.uuid4(), "what is mitosis?")

        assert result["syllabus_matches"] == [{"topic_name": "Mitosis", "score": 0.9}]
        assert result["chat_matches"] == [{"text": "past turn", "score": 0.7}]

    def test_syllabus_failure_does_not_break_chat_results(self):
        with patch("src.rag.retrieval.search_similar_chunks") as mock_syllabus, \
             patch("src.rag.retrieval.search_similar_chat_turns") as mock_chat:
            mock_syllabus.side_effect = ValueError("no collection yet")
            mock_chat.return_value = [{"text": "past turn", "score": 0.7}]

            result = retrieve_context(uuid.uuid4(), "what is mitosis?")

        assert result["syllabus_matches"] == []
        assert result["chat_matches"] == [{"text": "past turn", "score": 0.7}]

    def test_chat_failure_does_not_break_syllabus_results(self):
        with patch("src.rag.retrieval.search_similar_chunks") as mock_syllabus, \
             patch("src.rag.retrieval.search_similar_chat_turns") as mock_chat:
            mock_syllabus.return_value = [{"topic_name": "Mitosis", "score": 0.9}]
            mock_chat.side_effect = ValueError("no collection yet")

            result = retrieve_context(uuid.uuid4(), "what is mitosis?")

        assert result["syllabus_matches"] == [{"topic_name": "Mitosis", "score": 0.9}]
        assert result["chat_matches"] == []