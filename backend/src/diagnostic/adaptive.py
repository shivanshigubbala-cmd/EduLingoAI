"""Adaptive diagnostic flow — P3-SRE7.

Adaptivity model (per team decision): all questions are pre-generated in one
batch (P3-SRE6). This module does NOT call the LLM again per question —
instead it selects the ORDER questions are served in, based on whether the
previous answer was correct:

  - correct   -> next question comes from a DIFFERENT unit (breadth first)
  - incorrect -> next question comes from the SAME unit if one remains
                 (gather more signal on a shaky topic before moving on)
  - falls back to "any remaining question" if the preferred bucket is empty

Grading here is intentionally simple (exact match for MCQ, case-insensitive
substring match for short answers) — this is NOT the same as the LLM-rubric
grading used for quizzes (P6-SHR9); the diagnostic just needs a quick
right/wrong signal to drive adaptivity and mastery scoring (P3-SHI6), not
detailed feedback.
"""
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session as DBSession

from src.db.models import ChatMessage, MessageRole, SyllabusTopic


def grade_answer(question: dict[str, Any], answer_text: str) -> bool:
    """Return True if answer_text is considered correct for this question."""
    correct = question["correct_answer"].strip().lower()
    given = answer_text.strip().lower()

    if question["question_type"] == "mcq":
        return given == correct

    # short_answer: lenient containment check either direction
    return given == correct or given in correct or correct in given


def record_answer(
    db: DBSession,
    session_id: uuid.UUID,
    question_message_id: uuid.UUID,
    answer_text: str,
) -> bool:
    """Grade the answer, persist it as a ChatMessage, return is_correct."""
    question_message = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == question_message_id, ChatMessage.session_id == session_id)
        .first()
    )
    if question_message is None:
        raise ValueError("Question not found in this session.")

    question_data = json.loads(question_message.content)
    is_correct = grade_answer(question_data, answer_text)

    answer_message = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role=MessageRole.user,
        content=json.dumps({
            "question_message_id": str(question_message_id),
            "answer_text": answer_text,
            "is_correct": is_correct,
        }),
        topic_reference_id=question_message.topic_reference_id,
    )
    db.add(answer_message)
    db.commit()

    return is_correct


def _answered_question_ids(db: DBSession, session_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of question_message_ids that already have a recorded answer."""
    answer_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.role == MessageRole.user)
        .all()
    )
    answered = set()
    for msg in answer_messages:
        data = json.loads(msg.content)
        answered.add(uuid.UUID(data["question_message_id"]))
    return answered


def _unit_id_for_topic(db: DBSession, topic_id: uuid.UUID | None) -> uuid.UUID | None:
    if topic_id is None:
        return None
    topic_row = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if topic_row is None:
        return None
    return topic_row.parent_id


def select_next_question(
    db: DBSession,
    session_id: uuid.UUID,
    last_was_correct: bool | None = None,
    last_topic_id: uuid.UUID | None = None,
) -> ChatMessage | None:
    """Pick the next unanswered question for this session.

    Args:
        last_was_correct: whether the immediately-preceding answer was
            correct. None if this is the very first question being served.
        last_topic_id: topic_reference_id of the immediately-preceding
            question, used to compute its unit for the adaptive rule.

    Returns:
        The next ChatMessage (role=assistant, i.e. a question) to serve,
        or None if every question in the session has been answered.
    """
    answered_ids = _answered_question_ids(db, session_id)

    all_questions = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.role == MessageRole.assistant)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    remaining = [q for q in all_questions if q.id not in answered_ids]

    if not remaining:
        return None

    if last_was_correct is None:
        # First question being served — take the earliest-generated one.
        return remaining[0]

    last_unit_id = _unit_id_for_topic(db, last_topic_id)

    if last_unit_id is not None:
        if last_was_correct:
            different_unit = [
                q for q in remaining
                if _unit_id_for_topic(db, q.topic_reference_id) != last_unit_id
            ]
            if different_unit:
                return different_unit[0]
        else:
            same_unit = [
                q for q in remaining
                if _unit_id_for_topic(db, q.topic_reference_id) == last_unit_id
            ]
            if same_unit:
                return same_unit[0]

    return remaining[0]