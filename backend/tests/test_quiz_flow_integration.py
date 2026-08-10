"""Integration test for the full quiz flow — P6-SHR8 generation into
P6-SHR9 grading — using a real in-memory DB and mocked LLM calls only.
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
from src.db.models import (
    Document,
    DocumentStatus,
    Session as UserSession,
    SessionType,
    SyllabusTopic,
    TopicLevel,
)
from src.auth.dependencies import get_current_user_id
from src.documents.routes import router as documents_router
from src.quiz.router import router as quiz_router

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
app.include_router(quiz_router)
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user_id] = override_get_current_user_id
client = TestClient(app)


@patch("src.documents.routes.generate_quiz_questions")
def test_full_generate_then_grade_mcq_flow(mock_generate):
    db = TestingSessionLocal()
    document = Document(
        user_id=TEST_USER_ID,
        filename="test.pdf",
        storage_path="fake/path.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    db.add(document)
    db.flush()
    topic = SyllabusTopic(
        user_id=TEST_USER_ID,
        document_id=document.id,
        name="Weak Topic",
        level=TopicLevel.topic,
        mastery=0.1,
    )
    db.add(topic)
    db.commit()
    document_id, topic_id = document.id, topic.id
    db.close()

    mock_generate.return_value = [
        {
            "id": uuid.uuid4(),
            "topic_id": topic_id,
            "topic_name": "Weak Topic",
            "question_type": "mcq",
            "question_text": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "correct_answer": "4",
        }
    ]

    # Step 1: generate the quiz
    gen_response = client.post(f"/documents/{document_id}/quiz")
    assert gen_response.status_code == 200
    quiz_result_id = gen_response.json()["questions"][0]["id"]

    # Step 2: submit a CORRECT answer
    answer_response = client.post(
        f"/quiz/{quiz_result_id}/answer", json={"answer_text": "4"}
    )
    assert answer_response.status_code == 200
    body = answer_response.json()
    assert body["is_correct"] is True
    assert body["score"] == 1.0

    # The final answer triggers P7-TEAM3 automatically: it applies the quiz
    # score to mastery and saves an immutable schedule version.
    db = TestingSessionLocal()
    assert db.get(SyllabusTopic, topic_id).mastery == 1.0
    assert (
        db.query(UserSession)
        .filter(UserSession.user_id == TEST_USER_ID, UserSession.type == SessionType.schedule)
        .count()
        == 1
    )
    db.close()


@patch("src.documents.routes.generate_quiz_questions")
def test_full_generate_then_grade_wrong_mcq_answer(mock_generate):
    db = TestingSessionLocal()
    document = Document(
        user_id=TEST_USER_ID,
        filename="test2.pdf",
        storage_path="fake/path2.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    db.add(document)
    db.flush()
    topic = SyllabusTopic(
        user_id=TEST_USER_ID,
        document_id=document.id,
        name="Another Topic",
        level=TopicLevel.topic,
        mastery=0.5,
    )
    db.add(topic)
    db.commit()
    document_id, topic_id = document.id, topic.id
    db.close()

    mock_generate.return_value = [
        {
            "id": uuid.uuid4(),
            "topic_id": topic_id,
            "topic_name": "Another Topic",
            "question_type": "mcq",
            "question_text": "What is the capital of France?",
            "options": ["London", "Berlin", "Paris", "Rome"],
            "correct_answer": "Paris",
        }
    ]

    gen_response = client.post(f"/documents/{document_id}/quiz")
    quiz_result_id = gen_response.json()["questions"][0]["id"]

    answer_response = client.post(
        f"/quiz/{quiz_result_id}/answer", json={"answer_text": "London"}
    )
    body = answer_response.json()
    assert body["is_correct"] is False
    assert body["score"] == 0.0


def test_answer_unknown_quiz_result_returns_404():
    response = client.post(f"/quiz/{uuid.uuid4()}/answer", json={"answer_text": "anything"})
    assert response.status_code == 404
