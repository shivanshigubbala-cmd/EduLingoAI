"""Integration tests for POST /documents/{id}/quiz — P6-SHR8 endpoint wiring.

Mocks generate_quiz_questions (the LLM-calling function, already covered by
its own unit tests in test_quiz_generator.py) so this test can run without
Ollama installed/running — it verifies the endpoint's own logic: document
lookup, topic-row querying, error handling, and response shaping.

Uses an in-memory SQLite DB, same StaticPool pattern as other endpoint
integration tests in this project.
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
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel
from src.auth.dependencies import get_current_user_id
from src.documents.routes import router as documents_router

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
app.include_router(documents_router)
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user_id] = override_get_current_user_id
client = TestClient(app)


def _make_document_with_topics(db, mastery_map: dict[str, float]):
    document = Document(
        user_id=TEST_USER_ID,
        filename="test.pdf",
        storage_path="fake/path.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    db.add(document)
    db.flush()

    for name, mastery in mastery_map.items():
        db.add(
            SyllabusTopic(
                user_id=TEST_USER_ID,
                document_id=document.id,
                name=name,
                level=TopicLevel.topic,
                mastery=mastery,
            )
        )
    db.commit()
    return document.id


@patch("src.documents.routes.generate_quiz_questions")
def test_quiz_endpoint_returns_generated_questions(mock_generate):
    db = TestingSessionLocal()
    document_id = _make_document_with_topics(db, {"Weak Topic": 0.1, "Strong Topic": 0.9})
    db.close()

    mock_generate.return_value = [
        {
            "id": uuid.uuid4(),
            "topic_id": uuid.uuid4(),
            "topic_name": "Weak Topic",
            "question_type": "mcq",
            "question_text": "What is X?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
        }
    ]

    response = client.post(f"/documents/{document_id}/quiz")

    assert response.status_code == 200
    body = response.json()
    assert "quiz_id" in body
    assert len(body["questions"]) == 1
    assert body["questions"][0]["topic_name"] == "Weak Topic"
    # correct_answer must never reach the client
    assert "correct_answer" not in body["questions"][0]


@patch("src.documents.routes.generate_quiz_questions")
def test_quiz_endpoint_passes_mastery_scores_through(mock_generate):
    """Confirms the endpoint reads real mastery from the DB and forwards it —
    the actual weighting math is tested separately in test_quiz_generator.py."""
    db = TestingSessionLocal()
    document_id = _make_document_with_topics(db, {"Topic A": 0.2})
    db.close()

    mock_generate.return_value = []

    client.post(f"/documents/{document_id}/quiz")

    call_args = mock_generate.call_args
    topics_passed = call_args.args[0] if call_args.args else call_args.kwargs["topics"]
    assert topics_passed[0]["mastery"] == 0.2
    assert topics_passed[0]["name"] == "Topic A"


def test_quiz_endpoint_404_for_unknown_document():
    response = client.post(f"/documents/{uuid.uuid4()}/quiz")
    assert response.status_code == 404


def test_quiz_endpoint_404_when_no_topics_extracted():
    db = TestingSessionLocal()
    document = Document(
        user_id=TEST_USER_ID,
        filename="empty.pdf",
        storage_path="fake/empty.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.pending,
    )
    db.add(document)
    db.commit()
    document_id = document.id
    db.close()

    response = client.post(f"/documents/{document_id}/quiz")

    assert response.status_code == 404
    assert "Run extraction first" in response.json()["detail"]


@patch("src.documents.routes.generate_quiz_questions")
def test_quiz_endpoint_502_on_generation_failure(mock_generate):
    db = TestingSessionLocal()
    document_id = _make_document_with_topics(db, {"Topic A": 0.5})
    db.close()

    mock_generate.side_effect = ValueError("LLM returned garbage")

    response = client.post(f"/documents/{document_id}/quiz")

    assert response.status_code == 502