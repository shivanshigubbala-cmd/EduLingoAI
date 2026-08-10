"""FastAPI application entrypoint.

Run locally with:
    uvicorn src.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.documents.routes import router as documents_router
from src.diagnostic.router import router as diagnostic_router
from src.scheduling.routes import router as scheduling_router
from src.rag.router import router as rag_router
from src.quiz.router import router as quiz_router
from src.rag.chat_router import router as chat_router


app = FastAPI(title="EduLingoAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(diagnostic_router)
app.include_router(scheduling_router)
app.include_router(rag_router)
app.include_router(quiz_router)
app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}