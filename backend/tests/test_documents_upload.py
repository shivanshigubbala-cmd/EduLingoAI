"""Tests for P2-SHR2 — file upload endpoint.

Covers validation logic (file type, empty file) without needing a live DB.

NOTE: the `documents` table uses Postgres's native UUID column type
(db/models.py, from P0-SRE2), so a full upload -> DB row round-trip can't be
tested against SQLite here. That path is verified against the real Postgres
container: `docker compose up db` then hit POST /documents/upload with a
running backend (see README "Running locally"). CI/prod both use the same
Postgres service defined in docker-compose.yml, so this isn't a gap in
coverage for how the app actually runs — just a limitation of this fast
local test file.
"""
import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.documents.routes import router as documents_router

app = FastAPI()
app.include_router(documents_router)
client = TestClient(app)


def test_upload_rejects_unsupported_type():
    fake_txt = io.BytesIO(b"just text")
    response = client.post(
        "/documents/upload",
        files={"file": ("notes.txt", fake_txt, "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file():
    empty = io.BytesIO(b"")
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.png", empty, "image/png")},
    )
    assert response.status_code == 400