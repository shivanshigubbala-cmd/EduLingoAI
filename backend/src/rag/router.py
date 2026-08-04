"""RAG query routes — P5-SRE9 similarity search."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_current_user_id
from src.rag.store import search_similar_chunks

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