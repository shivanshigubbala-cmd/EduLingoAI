"""Diagnostic session persistence — P3-SRE6."""
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session as DBSession

from src.db.models import (
    ChatMessage,
    MessageRole,
    Session as SessionModel,
    SessionType,
    SyllabusTopic,
    TopicLevel,
)


def create_diagnostic_session(
    db: DBSession,
    user_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
    questions: list[dict[str, Any]],
) -> tuple[SessionModel, list[ChatMessage]]:
    """Create a diagnostic Session row and one ChatMessage per question.

    Matches each question's topic_name to the corresponding SyllabusTopic row
    (level == topic) for this document, so topic_reference_id is set whenever
    possible. Falls back to None if no exact match is found (e.g. LLM typo),
    rather than failing the whole request.

    Returns:
        (session, chat_messages) — chat_messages each hold the FULL question
        (including correct_answer) in their `content` field as JSON. Callers
        must strip correct_answer before returning anything to a client.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id

    topic_rows = (
        db.query(SyllabusTopic)
        .filter(
            SyllabusTopic.user_id == u_id,
            SyllabusTopic.document_id == d_id,
            SyllabusTopic.level == TopicLevel.topic,
        )
        .all()
    )
    name_to_id = {t.name.strip().lower(): t.id for t in topic_rows}

    session = SessionModel(
        id=uuid.uuid4(),
        user_id=u_id,
        type=SessionType.diagnostic,
    )
    db.add(session)
    db.flush()  # get session.id without a full commit yet

    messages: list[ChatMessage] = []
    for q in questions:
        topic_id = name_to_id.get(q["topic_name"].strip().lower())
        message = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role=MessageRole.assistant,
            content=json.dumps(q),
            topic_reference_id=topic_id,
        )
        db.add(message)
        messages.append(message)

    db.commit()
    db.refresh(session)
    return session, messages