"""FastAPI application entrypoint.

Run locally with:
    uvicorn src.main:app --reload --port 8000
"""
from fastapi import FastAPI

from src.documents.routes import router as documents_router

app = FastAPI(title="EduLingoAI API")

app.include_router(documents_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}