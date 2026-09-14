import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, Header, HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AuthSession, Role, User


password_hasher = PasswordHash.recommended()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Principal:
    session: AuthSession
    user: User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not password_hasher.verify(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User) -> tuple[AuthSession, str, str]:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=hash_secret(token),
        csrf_hash=hash_secret(csrf_token),
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_hours),
    )
    db.add(auth_session)
    db.commit()
    return auth_session, token, csrf_token


def get_principal(
    session_id: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_secret(session_id))
    )
    if auth_session is None or as_utc(auth_session.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = db.scalar(
        select(User).where(
            User.id == auth_session.user_id,
            User.tenant_id == auth_session.tenant_id,
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return Principal(session=auth_session, user=user)


def require_csrf(
    principal: Principal = Depends(get_principal),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Principal:
    if not csrf_token or not secrets.compare_digest(
        principal.session.csrf_hash, hash_secret(csrf_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token"
        )
    return principal


def require_teacher(principal: Principal = Depends(require_csrf)) -> Principal:
    if principal.user.role is not Role.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return principal


def require_teacher_read(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.user.role is not Role.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return principal


def require_student(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.user.role is not Role.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return principal
