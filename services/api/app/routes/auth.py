import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import (
    Principal,
    authenticate_user,
    create_session,
    get_principal,
    hash_secret,
    require_csrf,
)
from app.config import get_settings
from app.db import get_db
from app.models import (
    Assignment,
    AssignmentState,
    AuthSession,
    Enrollment,
    PacketRevision,
    PacketStatus,
    Role,
    User,
)
from app.schemas import LoginRequest, SessionResponse, UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])
DEMO_VISITOR_COOKIE = "demo_visitor"
DEMO_VISITOR_USERNAME_PREFIX = "demo-visitor-"


def isolated_demo_student(
    db: Session, visitor_token: str | None
) -> tuple[User, str]:
    """Return a browser-isolated synthetic learner with a fresh assignment."""
    token = visitor_token or secrets.token_urlsafe(32)
    username = f"{DEMO_VISITOR_USERNAME_PREFIX}{hash_secret(token)}"
    existing = db.scalar(
        select(User).where(User.username == username, User.role == Role.student)
    )
    if existing is not None:
        return existing, token

    source_user = db.scalar(
        select(User).where(User.username == "ada.demo", User.role == Role.student)
    )
    if source_user is None:
        raise HTTPException(status_code=503, detail="Run the synthetic demo seed first")
    source_enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.tenant_id == source_user.tenant_id,
            Enrollment.user_id == source_user.id,
        )
    )
    if source_enrollment is None:
        raise HTTPException(status_code=503, detail="Run the synthetic demo seed first")
    source = db.execute(
        select(Assignment, PacketRevision)
        .join(PacketRevision, PacketRevision.id == Assignment.packet_revision_id)
        .where(
            Assignment.tenant_id == source_user.tenant_id,
            Assignment.student_id == source_enrollment.student_id,
            Assignment.superseded_at.is_(None),
            PacketRevision.status == PacketStatus.published,
        )
        .order_by(Assignment.delivered_at.desc())
    ).first()
    if source is None:
        raise HTTPException(
            status_code=503,
            detail="Publish the synthetic demo packet before opening learner view",
        )
    source_assignment, packet = source
    visitor = User(
        tenant_id=source_user.tenant_id,
        username=username,
        display_name=source_user.display_name,
        password_hash=source_user.password_hash,
        role=Role.student,
    )
    db.add(visitor)
    db.flush()
    enrollment = Enrollment(
        tenant_id=source_user.tenant_id,
        class_id=source_enrollment.class_id,
        user_id=visitor.id,
    )
    db.add(enrollment)
    db.flush()
    db.add(
        Assignment(
            tenant_id=source_assignment.tenant_id,
            class_id=source_assignment.class_id,
            student_id=enrollment.student_id,
            lesson_id=source_assignment.lesson_id,
            packet_revision_id=packet.id,
            state=AssignmentState.assigned,
        )
    )
    return visitor, token


@router.post("/demo/{role}", response_model=SessionResponse)
def demo_session(
    role: Role,
    response: Response,
    demo_visitor: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """Enter a seeded role without credentials in local demo mode."""
    if get_settings().app_environment != "development":
        raise HTTPException(status_code=404)
    if role is Role.student:
        user, visitor_token = isolated_demo_student(db, demo_visitor)
        response.set_cookie(
            DEMO_VISITOR_COOKIE,
            visitor_token,
            httponly=True,
            secure=get_settings().cookie_secure,
            samesite="lax",
            max_age=get_settings().session_hours * 3600,
        )
    else:
        user = db.scalar(
            select(User).where(
                User.username == "teacher.demo", User.role == Role.teacher
            )
        )
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
