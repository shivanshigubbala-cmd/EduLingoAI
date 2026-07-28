"""HTTP routes for topic-tree extraction, retrieval, and partial updates — P2-SHI4/5/6."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.models import Document
from src.db.session import get_db
from src.topic_tree.extractor import extract_topic_tree
from src.topic_tree.persistence import get_topic_tree, persist_topic_tree, update_topic

router = APIRouter(prefix="/documents", tags=["topic_tree"])

# TODO(P2-SHR3): Replace this placeholder string with real text extracted from PDF/image OCR pipeline
STUB_PARSED_TEXT = """
Physics 101 Course Syllabus:
Unit 1: Mechanics. Topics include Kinematics (subtopics: Vectors, Motion in 1D, Projectile Motion)
and Newton's Laws (subtopics: First Law, Second Law, Third Law).
Unit 2: Electromagnetism. Topics include Electrostatics (subtopics: Coulomb's Law, Electric Fields)
and Magnetism (subtopics: Magnetic Fields, Lorentz Force).
"""


class TopicUpdatePayload(BaseModel):
    name: str | None = Field(default=None, description="Optional updated name for the topic")
    subtopics: list[str] | None = Field(default=None, description="Optional updated list of subtopics")


def _verify_document_access(db: Session, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    """Verify document exists and belongs to the current user.

    Raises 404 if document does not exist or user is unauthorized to prevent info leaking.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or doc.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc


@router.post("/{document_id}/extract", status_code=200)
def extract_document_topics(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Extract topic tree from document text and persist to syllabus_topics table.

    TODO(P2-SHR3): Wire in real extracted text from PDF/OCR pipeline instead of STUB_PARSED_TEXT.
    """
    _verify_document_access(db, document_id, user_id)

    # 1. Extract topic tree from text
    tree_dict = extract_topic_tree(STUB_PARSED_TEXT)

    # 2. Flatten and persist to database
    persist_topic_tree(db, user_id, document_id, tree_dict)

    # 3. Retrieve and return persisted tree
    persisted_tree = get_topic_tree(db, user_id, document_id)
    if not persisted_tree:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve topic tree after extraction",
        )
    return persisted_tree


@router.get("/{document_id}/topics", status_code=200)
def get_document_topics(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Retrieve existing topic tree for a document."""
    _verify_document_access(db, document_id, user_id)

    tree = get_topic_tree(db, user_id, document_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No topic tree found for this document",
        )
    return tree


@router.patch("/{document_id}/topics/{topic_id}", status_code=200)
def patch_document_topic(
    document_id: uuid.UUID,
    topic_id: uuid.UUID,
    payload: TopicUpdatePayload,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Partially update a topic's name and/or subtopics without altering mastery scores or sibling topics."""
    _verify_document_access(db, document_id, user_id)

    updated = update_topic(
        db=db,
        user_id=user_id,
        document_id=document_id,
        topic_id=topic_id,
        name=payload.name,
        subtopics=payload.subtopics,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found for this document",
        )

    tree = get_topic_tree(db, user_id, document_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No topic tree found after update",
        )
    return tree
