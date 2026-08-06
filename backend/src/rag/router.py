"""RAG query routes — P5-SRE9 similarity search."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_current_user_id
from src.rag.store import search_similar_chunks
from src.rag.chat_store import embed_chat_turn
from src.rag.retrieval import retrieve_context
from sqlalchemy.orm import Session
from src.db.session import get_db

router = APIRouter(prefix="/rag", tags=["rag"])


class SimilaritySearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/search")
def search(
    request: SimilaritySearchRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Return the most similar syllabus chunks for this user's query."""
    try:
        results = search_similar_chunks(user_id, request.query, limit=request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"results": results}

class RetrievalRequest(BaseModel):
    query: str
    topic_limit: int = 3
    chat_limit: int = 3


@router.post("/retrieve")
def retrieve(
    request: RetrievalRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Given a doubt, return the relevant syllabus topic(s) + related past chat turns (P5-SRE10)."""
    return retrieve_context(
        user_id, request.query, topic_limit=request.topic_limit, chat_limit=request.chat_limit
    )


@router.post("/chat-turns/{message_id}/embed")
def embed_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Manually embed an existing chat message (for testing until P5-SHR7 auto-embeds new messages)."""
    try:
        embed_chat_turn(db, user_id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"message": "Chat turn embedded successfully."}