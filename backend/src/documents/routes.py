"""File upload endpoint — P2-SHR2.

Accepts pdf/png/jpg, stores the file on disk, writes a `documents` row
(schema from P0-SRE2 / db/models.py), and returns a document_id.
"""
import json
import uuid
from pathlib import Path
from src.ocr.pdf_extractor import extract_pdf_text_as_string, PDFExtractionError
from src.ocr.handwriting_ocr import transcribe_handwriting, OCRError
from src.topic_tree import extract_topic_tree, persist_topic_tree, get_topic_tree
from src.topic_tree.schemas import TopicTreeResponse
from src.rag.store import embed_document_topics
from src.quiz.generator import generate_quiz_questions
from src.quiz.schemas import QuizResponse, QuizQuestionPublic
from src.diagnostic import (
    generate_diagnostic_questions,
    create_diagnostic_session,
    DiagnosticQuestionPublic,
    DiagnosticSessionResponse,
)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.config import get_settings
from src.db.session import get_db
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_ROOT = Path("uploads")
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def save_upload_to_disk(file_bytes: bytes, extension: str) -> str:
    """Write bytes to STORAGE_ROOT under a random filename. Returns the path."""
    stored_name = f"{uuid.uuid4()}{extension}"
    dest = STORAGE_ROOT / stored_name
    dest.write_bytes(file_bytes)
    return str(dest)


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed: pdf, png, jpg."
            ),
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    extension = ALLOWED_MIME_TYPES[file.content_type]
    storage_path = save_upload_to_disk(file_bytes, extension)

    document = Document(
        user_id=user_id,
        filename=file.filename,
        storage_path=storage_path,
        mime_type=file.content_type,
        status=DocumentStatus.pending,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "status": document.status.value,
    }


@router.post("/{document_id}/extract")
def extract_document_topics(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Run the full pipeline: parse text (PDF or handwritten image) -> LLM
    topic-tree extraction -> persist.

    Wires together P2-SHR3 (PDF text), P2-SHR4 (handwriting OCR), P2-SHI4
    (LLM extraction), and P2-SHI5 (persistence).
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    confidence_flag = False

    if document.mime_type == "application/pdf":
        try:
            parsed_text = extract_pdf_text_as_string(document.storage_path)
        except PDFExtractionError as exc:
            document.status = DocumentStatus.failed
            db.commit()
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    elif document.mime_type in IMAGE_MIME_TYPES:
        settings = get_settings()
        try:
            ocr_result = transcribe_handwriting(
                document.storage_path, settings.OCR_SPACE_API_KEY
            )
        except OCRError as exc:
            document.status = DocumentStatus.failed
            db.commit()
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        parsed_text = ocr_result["text"]
        confidence_flag = ocr_result["confidence_flag"]
        document.ocr_confidence = ocr_result["confidence"]

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for extraction: '{document.mime_type}'.",
        )

    try:
        tree = extract_topic_tree(parsed_text)
    except ValueError as exc:
        document.status = DocumentStatus.failed
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Topic-tree extraction failed: {exc}",
        ) from exc

    persist_topic_tree(db, user_id, document_id, tree)

    document.status = DocumentStatus.parsed
    db.commit()

    # Let the confirm screen (P2-SRE5) warn the student when handwriting was
    # low-confidence, so they know to double-check the extracted topics
    # rather than trusting them blindly.
    if confidence_flag:
        return {**tree, "ocr_confidence_flag": True}
    return tree


@router.get("/{document_id}/topics")
def get_document_topics(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Fetch the persisted topic tree for a document."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    tree = get_topic_tree(db, user_id, document_id)
    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="No topics found for this document. Run extraction first.",
        )

    return tree


@router.patch("/{document_id}/topics")
def update_document_topics(
    document_id: uuid.UUID,
    tree: TopicTreeResponse,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Save a user-edited topic tree (from the confirm/preview screen, P2-SRE5).

    `tree` is validated against TopicTreeResponse before persisting, so a malformed
    or empty body is rejected with a 422 instead of silently overwriting real data.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    persist_topic_tree(db, user_id, document_id, tree.model_dump())
    return tree.model_dump()


@router.post("/{document_id}/diagnostic", response_model=DiagnosticSessionResponse)
def generate_diagnostic(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Generate a capped diagnostic question set spanning this document's topic tree.

    P3-SRE6. Depends on P2-SHI5 (topic-tree persistence) — reads topic-level
    rows directly from syllabus_topics rather than re-running extraction.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    topic_rows = (
        db.query(SyllabusTopic)
        .filter(
            SyllabusTopic.user_id == user_id,
            SyllabusTopic.document_id == document_id,
            SyllabusTopic.level == TopicLevel.topic,
        )
        .all()
    )
    if not topic_rows:
        raise HTTPException(
            status_code=404,
            detail="No topics found for this document. Run extraction first.",
        )

    topic_names = [t.name for t in topic_rows]

    try:
        questions = generate_diagnostic_questions(topic_names)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Diagnostic question generation failed: {exc}",
        ) from exc

    session, chat_messages = create_diagnostic_session(db, user_id, document_id, questions)

    public_questions = [
        DiagnosticQuestionPublic(
            id=msg.id,
            topic_id=msg.topic_reference_id,
            topic_name=json.loads(msg.content)["topic_name"],
            question_type=json.loads(msg.content)["question_type"],
            question_text=json.loads(msg.content)["question_text"],
            options=json.loads(msg.content).get("options"),
        )
        for msg in chat_messages
    ]

    return DiagnosticSessionResponse(session_id=session.id, questions=public_questions)
@router.post("/{document_id}/embed")
def embed_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Embed a document's topic tree into the vector store (P5-SRE9)."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        count = embed_document_topics(db, user_id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"embedded_count": count}
@router.post("/{document_id}/quiz", response_model=QuizResponse)
def generate_quiz(
    document_id: uuid.UUID,
    max_questions: int = 10,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Generate a quiz weighted toward this document's lower-mastery topics.

    P6-SHR8. Depends on P2-SHI5 (topic-tree persistence, for topic rows) and
    P3-SHI6 (mastery scoring, for the weighting itself) — reads mastery
    directly from syllabus_topics, same as the diagnostic endpoint reads
    topic names.

    TODO(P6-SHR9): correct_answer is generated but NOT persisted anywhere —
    QuizResult has no column for it (only student_answer, is_correct, score,
    rationale). Auto-grading will need either a new migration adding a
    correct_answer column, or some other place to stash the answer key
    between generation and grading. Flagging now so it isn't a surprise.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    topic_rows = (
        db.query(SyllabusTopic)
        .filter(
            SyllabusTopic.user_id == user_id,
            SyllabusTopic.document_id == document_id,
            SyllabusTopic.level == TopicLevel.topic,
        )
        .all()
    )
    if not topic_rows:
        raise HTTPException(
            status_code=404,
            detail="No topics found for this document. Run extraction first.",
        )

    topics = [{"id": t.id, "name": t.name, "mastery": t.mastery} for t in topic_rows]

    try:
        questions = generate_quiz_questions(topics, max_questions=max_questions)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Quiz generation failed: {exc}",
        ) from exc

    quiz_id = uuid.uuid4()
    public_questions = [
        QuizQuestionPublic(
            id=q["id"],
            topic_id=q["topic_id"],
            topic_name=q["topic_name"],
            question_type=q["question_type"],
            question_text=q["question_text"],
            options=q.get("options"),
        )
        for q in questions
    ]

    return QuizResponse(quiz_id=quiz_id, questions=public_questions)