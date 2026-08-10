"""Auth dependencies for protected routes.

Real JWT cookie verification, per the stack agreed in docs/architecture.md
(P0-SHI1): backend issues a JWT on login, set as an httpOnly secure cookie,
verified here on each request.
"""
import uuid

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from src.db.models import User
from src.db.session import get_db
from .security import verify_access_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Verify the access_token cookie and return the full User row."""
    token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = verify_access_token(token)
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Return just the authenticated user's ID — used by routes that only
    need the ID (documents, diagnostic, scheduling, rag, quiz), not the
    full User object."""
    return current_user.id