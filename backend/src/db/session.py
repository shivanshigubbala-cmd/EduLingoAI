"""Database session management.

Provides a SQLAlchemy engine + session factory, and a FastAPI dependency
(`get_db`) that yields a session per-request and always closes it.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()