"""Doubt-answering chat endpoint — P5-SHR7.

Wires together P5-SRE10 (retrieval) and this module's answer_doubt() into
a real HTTP endpoint. Persists both the student's question and the
assistant's answer as ChatMessage rows, then auto-embeds them so future
doubts can retrieve this conversation as "related past turns" — closing
the loop that src/rag/chat_store.py's docstring flagged as pending.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.db.models import Session as ChatSession, SessionType, ChatMessage, MessageRole
from src.rag.retrieval import retrieve_context
from src.rag.chat_answer import answer_doubt
from src.rag.chat_store import embed_chat_turn

router = APIRouter(prefix="/chat", tags=["chat"])


class DoubtRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str


class DoubtResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    referenced_topic_id: uuid.UUID | None
    referenced_topic_name: str | None


@router.post("/ask", response_model=DoubtResponse)
def ask_doubt(
    request: DoubtRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Answer a student's doubt, grounded in their syllabus + past chat history.

    P5-SHR7. Depends on P5-SRE10 (retrieve_context).
    """
    if request.session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == request.session_id, ChatSession.user_id == user_id)
            .first()
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Chat session not found.")
    else:
        session = ChatSession(user_id=user_id, type=SessionType.chat)
        db.add(session)
        db.flush()

    user_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=request.message,
    )
    db.add(user_message)
    db.flush()

    retrieval = retrieve_context(user_id, request.message)

    try:
        result = answer_doubt(request.message, retrieval)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate an answer: {exc}") from exc

    assistant_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.assistant,
        content=result["answer"],
        topic_reference_id=result["referenced_topic_id"],
    )
    db.add(assistant_message)
    db.commit()

    # Auto-embed both turns so future doubts can retrieve this exchange as
    # "related past turns" — best-effort: a failed embed shouldn't fail the
    # whole request, since the student's answer is already generated.
    for message in (user_message, assistant_message):
        try:
            embed_chat_turn(db, user_id, message.id)
        except ValueError:
            pass

    return DoubtResponse(
        session_id=session.id,
        answer=result["answer"],
        referenced_topic_id=result["referenced_topic_id"],
        referenced_topic_name=result["referenced_topic_name"],
    )