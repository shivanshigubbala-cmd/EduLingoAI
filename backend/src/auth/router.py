from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from src.db.models import User
from src.db.session import get_db
from .dependencies import get_current_user
from .schemas import (
    SignupRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)
from .security import create_access_token
from .service import (
    create_user,
    get_user_by_email,
    authenticate_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/health")
def auth_health():
    return {
        "message": "Authentication module is working"
    }


@router.post(
    "/signup",
    response_model=TokenResponse,
)
def signup(
    request: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    existing_user = get_user_by_email(
        db,
        request.email,
    )
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )
    user = create_user(
        db,
        request.name,
        request.email,
        request.password,
    )
    token = create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # set True once served over HTTPS
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
        },
    }


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db,
        request.email,
        request.password,
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )
    token = create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
        },
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
    }
@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}