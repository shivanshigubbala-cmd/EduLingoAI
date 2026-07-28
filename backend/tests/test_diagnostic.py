"""Unit tests for backend/src/diagnostic/ — P3-SHI6 knowledge-level scoring."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
from src.diagnostic import DiagnosticAnswer, apply_mastery_scores, score_diagnostic
from src.topic_tree import persist_topic_tree


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


class TestDiagnosticScoring:

    def test_score_diagnostic_calculation_and_omission(self):
        """Assert score_diagnostic calculates difficulty-weighted mastery and omits unanswered topics."""
        topic_a_id = uuid.uuid4()
        topic_b_id = uuid.uuid4()

        stub_answers = [
            # Topic A: 1 hard question correct (diff 0.8), 1 easy question correct (diff 0.2) -> score = 1.0
            {
                "topic_id": topic_a_id,
                "question": "What is F=ma?",
                "is_correct": True,
                "difficulty": 0.8,
            },
            {
                "topic_id": topic_a_id,
                "question": "What is mass?",
                "is_correct": True,
                "difficulty": 0.2,
            },
            # Topic B: 1 hard question incorrect (diff 0.8), 1 easy question correct (diff 0.2)
            # Total weight = 1.0, earned weight = 0.2 -> score = 0.2 / 1.0 = 0.2
            {
                "topic_id": topic_b_id,
                "question": "Explain special relativity",
                "is_correct": False,
                "difficulty": 0.8,
            },
            {
                "topic_id": topic_b_id,
                "question": "What is speed of light symbol?",
                "is_correct": True,
                "difficulty": 0.2,
            },
        ]

        scores = score_diagnostic(stub_answers)

        # Assert only answered topics are present
        assert topic_a_id in scores
        assert topic_b_id in scores
        assert len(scores) == 2

        # Assert scores are floats in [0, 1]
        assert scores[topic_a_id] == 1.0
        assert scores[topic_b_id] == 0.2
        assert all(0.0 <= s <= 1.0 for s in scores.values())

    def test_score_diagnostic_accepts_pydantic_models(self):
        """Assert score_diagnostic accepts DiagnosticAnswer model instances directly."""
        topic_id = uuid.uuid4()
        answers = [
            DiagnosticAnswer(
                topic_id=topic_id,
                question="Q1",
                is_correct=False,
                difficulty=0.5,
            )
        ]
        scores = score_diagnostic(answers)
        assert scores[topic_id] == 0.0

    def test_apply_mastery_scores_updates_db_and_leaves_unanswered_null(
        self, db_session
    ):
        """Persist a topic tree, apply scores for a subset of topics, assert DB rows update correctly."""
        # 1. Setup User and Document
        user = User(
            id=uuid.uuid4(),
            email="diag_user@example.com",
            hashed_password="secret_pass",
            name="Diagnostic Student",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="physics.pdf",
            storage_path="/uploads/physics.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        # 2. Persist topic tree with 3 topics
        sample_tree = {
            "subject": "Physics",
            "units": [
                {
                    "name": "Mechanics",
                    "topics": [
                        {
                            "name": "Kinematics",
                            "subtopics": ["Vectors"],
                            "mastery": None,
                        },
                        {
                            "name": "Dynamics",
                            "subtopics": ["Forces"],
                            "mastery": None,
                        },
                        {
                            "name": "Energy",
                            "subtopics": ["Work"],
                            "mastery": None,
                        },
                    ],
                }
            ],
        }
        persisted_rows = persist_topic_tree(
            db_session, user_id=user.id, document_id=doc.id, tree=sample_tree
        )

        topic_rows = [r for r in persisted_rows if r.level == TopicLevel.topic]
        assert len(topic_rows) == 3

        topic_kinematics = topic_rows[0]
        topic_dynamics = topic_rows[1]
        topic_energy = topic_rows[2]

        # 3. Create diagnostic answers covering Kinematics & Dynamics ONLY (Energy left unanswered)
        answers = [
            {
                "topic_id": str(topic_kinematics.id),
                "question": "Kinematics Q1",
                "is_correct": True,
                "difficulty": 0.6,
            },
            {
                "topic_id": str(topic_dynamics.id),
                "question": "Dynamics Q1",
                "is_correct": False,
                "difficulty": 0.4,
            },
        ]

        scores = score_diagnostic(answers)

        # 4. Apply mastery scores to database
        updated_count = apply_mastery_scores(
            db_session,
            user_id=user.id,
            document_id=doc.id,
            scores=scores,
        )
        assert updated_count == 2

        # 5. Assert database state
        db_topics = (
            db_session.query(SyllabusTopic)
            .filter_by(user_id=user.id, document_id=doc.id)
            .all()
        )

        kinematics_db = next(t for t in db_topics if t.id == topic_kinematics.id)
        dynamics_db = next(t for t in db_topics if t.id == topic_dynamics.id)
        energy_db = next(t for t in db_topics if t.id == topic_energy.id)

        assert kinematics_db.mastery == 1.0
        assert dynamics_db.mastery == 0.0
        assert energy_db.mastery is None  # Remains NULL as specified
