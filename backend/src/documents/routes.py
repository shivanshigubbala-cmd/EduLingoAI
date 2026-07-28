"""File upload endpoint — P2-SHR2.

Accepts pdf/png/jpg, stores the file on disk, writes a `documents` row
(schema from P0-SRE2 / db/models.py), and returns a document_id.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.db.models import Document, DocumentStatus

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_ROOT = Path("uploads")
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

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