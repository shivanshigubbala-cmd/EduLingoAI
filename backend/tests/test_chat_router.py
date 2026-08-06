"""Integration test for POST /chat/ask — P5-SHR7.

Mocks retrieve_context, answer_doubt's LLM call, and embed_chat_turn (all
external — Qdrant/Ollama) so this runs without either service available.
Verifies the endpoint's own logic: session creation, message persistence,
and response shaping.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db import models
from src.db.session import get_db
from src.db.models import ChatMessage, Session as ChatSession
from src.auth.dependencies import get_current_user_id
from src.rag.chat_router import router as chat_router

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER_ID = uuid.uuid4()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user_id():
    return TEST_USER_ID


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


app = FastAPI()
app.include_router(chat_router)
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user_id] = override_get_current_user_id
client = TestClient(app)


@patch("src.rag.chat_router.embed_chat_turn")
@patch("src.rag.chat_router.answer_doubt")
@patch("src.rag.chat_router.retrieve_context")
def test_ask_creates_new_session_and_returns_grounded_answer(
    mock_retrieve, mock_answer, mock_embed
):
    topic_id = uuid.uuid4()
    mock_retrieve.return_value = {
        "syllabus_matches": [
            {"topic_id": str(topic_id), "topic_name": "Photosynthesis", "text": "...", "score": 0.9}
        ],
        "chat_matches": [],
    }
    mock_answer.return_value = {
        "answer": "Based on the topic 'Photosynthesis', plants convert light to energy.",
        "referenced_topic_id": topic_id,
        "referenced_topic_name": "Photosynthesis",
    }

    response = client.post("/chat/ask", json={"message": "How do plants make energy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["referenced_topic_name"] == "Photosynthesis"
    assert "session_id" in body

    # Verify both messages were actually persisted
    db = TestingSessionLocal()
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == uuid.UUID(body["session_id"]))
        .all()
    )
    assert len(messages) == 2
    db.close()


@patch("src.rag.chat_router.embed_chat_turn")
@patch("src.rag.chat_router.answer_doubt")
@patch("src.rag.chat_router.retrieve_context")
def test_ask_reuses_existing_session(mock_retrieve, mock_answer, mock_embed):
    db = TestingSessionLocal()
    from src.db.models import SessionType
    session = ChatSession(user_id=TEST_USER_ID, type=SessionType.chat)
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    mock_retrieve.return_value = {"syllabus_matches": [], "chat_matches": []}
    mock_answer.return_value = {
        "answer": "I don't have relevant syllabus content for that.",
        "referenced_topic_id": None,
        "referenced_topic_name": None,
    }

    response = client.post(
        "/chat/ask", json={"session_id": str(session_id), "message": "A follow-up question"}
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)


def test_ask_with_unknown_session_id_returns_404():
    response = client.post(
        "/chat/ask", json={"session_id": str(uuid.uuid4()), "message": "anything"}
    )
    assert response.status_code == 404