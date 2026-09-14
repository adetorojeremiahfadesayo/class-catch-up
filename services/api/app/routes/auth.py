from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import (
    Principal,
    authenticate_user,
    create_session,
    get_principal,
    require_csrf,
)
from app.config import get_settings
from app.db import get_db
from app.models import AuthSession, Role, User
from app.schemas import LoginRequest, SessionResponse, UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/demo/{role}", response_model=SessionResponse)
def demo_session(role: Role, response: Response, db: Session = Depends(get_db)):
    """Enter a seeded role without credentials in local demo mode."""
    if get_settings().app_environment != "development":
        raise HTTPException(status_code=404)
    username = "teacher.demo" if role is Role.teacher else "ada.demo"
    user = db.scalar(select(User).where(User.username == username, User.role == role))
    if user is None:
        raise HTTPException(status_code=503, detail="Run the synthetic demo seed first")
    _, token, csrf_token = create_session(db, user)
    response.set_cookie(
        "session_id", token, httponly=True, secure=get_settings().cookie_secure,
        samesite="lax", max_age=get_settings().session_hours * 3600,
    )
    return SessionResponse(
        user_id=user.id, display_name=user.display_name,
        role=user.role.value, csrf_token=csrf_token,
    )


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    _, token, csrf_token = create_session(db, user)
    response.set_cookie(
        "session_id",
        token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        max_age=get_settings().session_hours * 3600,
    )
    return SessionResponse(
        user_id=user.id,
        display_name=user.display_name,
        role=user.role.value,
        csrf_token=csrf_token,
    )


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(get_principal)):
    return principal.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    db.execute(delete(AuthSession).where(AuthSession.id == principal.session.id))
    db.commit()
    response.delete_cookie("session_id")
