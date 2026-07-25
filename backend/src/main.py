from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router

# Import models so SQLAlchemy registers all tables
from src.db import models
from src.db.base import Base
from src.db.session import engine

app = FastAPI(
    title="EduLingoAI Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.on_event("startup")
def startup():
    # Create all database tables if they don't exist
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "message": "EduLingoAI Backend Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }