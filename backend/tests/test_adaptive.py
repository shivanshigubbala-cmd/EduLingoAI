"""Tests for backend/src/diagnostic/adaptive.py — P3-SRE7 adaptive diagnostic flow."""

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import (
    ChatMessage,
    Document,
    DocumentStatus,
    MessageRole,
    Session as SessionModel,
    SessionType,
    SyllabusTopic,
    TopicLevel,
    User,
)
from src.diagnostic.adaptive import grade_answer, record_answer, select_next_question


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


@pytest.fixture
def seeded_session(db_session):
    """Build a user + document + two units (each with one topic) + a diagnostic
    session with one question per topic, mirroring what P3-SRE6 would produce."""
    user = User(
        id=uuid.uuid4(), email="student@example.com", hashed_password="x", name="Student"
    )
    doc = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        filename="notes.pdf",
        storage_path="/uploads/notes.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    unit_a = SyllabusTopic(
        id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=None,
        name="Mechanics", level=TopicLevel.unit,
    )
    unit_b = SyllabusTopic(
        id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=None,
        name="Electromagnetism", level=TopicLevel.unit,
    )
    topic_a = SyllabusTopic(
        id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=unit_a.id,
        name="Kinematics", level=TopicLevel.topic,
    )
    topic_b = SyllabusTopic(
        id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=unit_b.id,
        name="Electrostatics", level=TopicLevel.topic,
    )
    db_session.add_all([user, doc, unit_a, unit_b, topic_a, topic_b])
    db_session.commit()

    diag_session = SessionModel(id=uuid.uuid4(), user_id=user.id, type=SessionType.diagnostic)
    db_session.add(diag_session)
    db_session.flush()

    question_a = ChatMessage(
        id=uuid.uuid4(),
        session_id=diag_session.id,
        role=MessageRole.assistant,
        content=json.dumps({
            "topic_name": "Kinematics",
            "question_type": "mcq",
            "question_text": "What is velocity?",
            "options": ["Speed", "Rate of displacement", "Force", "Mass"],
            "correct_answer": "Rate of displacement",
        }),
        topic_reference_id=topic_a.id,
    )
    question_b = ChatMessage(
        id=uuid.uuid4(),
        session_id=diag_session.id,
        role=MessageRole.assistant,
        content=json.dumps({
            "topic_name": "Electrostatics",
            "question_type": "short_answer",
            "question_text": "State Coulomb's Law.",
            "options": None,
            "correct_answer": "Force is proportional to charges and inversely to distance squared",
        }),
        topic_reference_id=topic_b.id,
    )
    db_session.add_all([question_a, question_b])
    db_session.commit()

    return {
        "session": diag_session,
        "unit_a": unit_a,
        "unit_b": unit_b,
        "topic_a": topic_a,
        "topic_b": topic_b,
        "question_a": question_a,
        "question_b": question_b,
    }


class TestGradeAnswer:
    def test_mcq_exact_match_correct(self):
        question = {"question_type": "mcq", "correct_answer": "Rate of displacement"}
        assert grade_answer(question, "Rate of displacement") is True

    def test_mcq_case_insensitive(self):
        question = {"question_type": "mcq", "correct_answer": "Rate of displacement"}
        assert grade_answer(question, "RATE OF DISPLACEMENT") is True

    def test_mcq_wrong_option(self):
        question = {"question_type": "mcq", "correct_answer": "Rate of displacement"}
        assert grade_answer(question, "Speed") is False

    def test_short_answer_lenient_containment(self):
        question = {"question_type": "short_answer", "correct_answer": "chlorophyll"}
        assert grade_answer(question, "it's chlorophyll") is True

    def test_short_answer_wrong(self):
        question = {"question_type": "short_answer", "correct_answer": "chlorophyll"}
        assert grade_answer(question, "hemoglobin") is False


class TestRecordAnswer:
    def test_records_correct_answer(self, db_session, seeded_session):
        s = seeded_session
        is_correct = record_answer(
            db_session, s["session"].id, s["question_a"].id, "Rate of displacement"
        )
        assert is_correct is True

        stored = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.session_id == s["session"].id, ChatMessage.role == MessageRole.user)
            .first()
        )
        assert stored is not None
        data = json.loads(stored.content)
        assert data["is_correct"] is True
        assert data["question_message_id"] == str(s["question_a"].id)

    def test_records_incorrect_answer(self, db_session, seeded_session):
        s = seeded_session
        is_correct = record_answer(db_session, s["session"].id, s["question_a"].id, "Speed")
        assert is_correct is False

    def test_raises_on_unknown_question(self, db_session, seeded_session):
        s = seeded_session
        with pytest.raises(ValueError, match="not found"):
            record_answer(db_session, s["session"].id, uuid.uuid4(), "anything")


class TestSelectNextQuestion:
    def test_first_question_has_no_prior_answer(self, db_session, seeded_session):
        s = seeded_session
        next_q = select_next_question(db_session, s["session"].id, last_was_correct=None)
        assert next_q is not None
        assert next_q.id in {s["question_a"].id, s["question_b"].id}

    def test_correct_answer_moves_to_different_unit(self, db_session, seeded_session):
        s = seeded_session
        # Answer question_a (unit_a) correctly -> next should be question_b (unit_b)
        record_answer(db_session, s["session"].id, s["question_a"].id, "Rate of displacement")
        next_q = select_next_question(
            db_session, s["session"].id, last_was_correct=True, last_topic_id=s["topic_a"].id
        )
        assert next_q.id == s["question_b"].id

    def test_incorrect_answer_stays_in_same_unit_if_available(self, db_session, seeded_session):
        s = seeded_session
        # Add a second question in unit_a so there's something to stay on.
        topic_a2 = SyllabusTopic(
            id=uuid.uuid4(), user_id=s["session"].user_id, document_id=s["question_a"].id,
            parent_id=s["unit_a"].id, name="Newton's Laws", level=TopicLevel.topic,
        )
        db_session.add(topic_a2)
        db_session.commit()

        question_a2 = ChatMessage(
            id=uuid.uuid4(),
            session_id=s["session"].id,
            role=MessageRole.assistant,
            content=json.dumps({
                "topic_name": "Newton's Laws",
                "question_type": "short_answer",
                "question_text": "State the first law.",
                "options": None,
                "correct_answer": "An object at rest stays at rest",
            }),
            topic_reference_id=topic_a2.id,
        )
        db_session.add(question_a2)
        db_session.commit()

        record_answer(db_session, s["session"].id, s["question_a"].id, "Speed")  # wrong
        next_q = select_next_question(
            db_session, s["session"].id, last_was_correct=False, last_topic_id=s["topic_a"].id
        )
        assert next_q.id == question_a2.id

    def test_returns_none_when_all_questions_answered(self, db_session, seeded_session):
        s = seeded_session
        record_answer(db_session, s["session"].id, s["question_a"].id, "Rate of displacement")
        record_answer(db_session, s["session"].id, s["question_b"].id, "Coulomb's law answer")
        next_q = select_next_question(
            db_session, s["session"].id, last_was_correct=True, last_topic_id=s["topic_b"].id
        )
        assert next_q is None