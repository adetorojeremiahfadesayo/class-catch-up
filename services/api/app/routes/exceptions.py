from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_teacher, require_teacher_read
from app.db import get_db
from app.models import Assignment, ExceptionRecord, SchoolClass
from app.schemas import ExceptionResponse, TeacherAssignmentResponse


router = APIRouter(prefix="/teacher", tags=["teacher-dashboard"])


def teacher_class_ids(db: Session, principal: Principal) -> list[str]:
    return list(
        db.scalars(
            select(SchoolClass.id).where(
                SchoolClass.tenant_id == principal.user.tenant_id,
                SchoolClass.owner_teacher_id == principal.user.id,
            )
        ).all()
    )


@router.get("/exceptions", response_model=list[ExceptionResponse])
def list_exceptions(
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    class_ids = teacher_class_ids(db, principal)
    return db.scalars(
        select(ExceptionRecord)
        .where(
            ExceptionRecord.tenant_id == principal.user.tenant_id,
            ExceptionRecord.class_id.in_(class_ids),
            ExceptionRecord.open.is_(True),
        )
        .order_by(ExceptionRecord.created_at.desc())
    ).all()


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(
    exception_id: str,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    class_ids = teacher_class_ids(db, principal)
    exception = db.scalar(
        select(ExceptionRecord).where(
            ExceptionRecord.id == exception_id,
            ExceptionRecord.tenant_id == principal.user.tenant_id,
            ExceptionRecord.class_id.in_(class_ids),
        )
    )
    if exception is None:
        raise HTTPException(status_code=404)
    exception.open = False
    exception.resolved_at = datetime.now(UTC)
    db.flush()
    assignment = db.scalar(select(Assignment).where(
        Assignment.id == exception.source_event_id,
        Assignment.tenant_id == principal.user.tenant_id,
    ))
    if assignment is not None:
        remaining = db.scalar(select(ExceptionRecord.id).where(
            ExceptionRecord.source_event_id == assignment.id,
            ExceptionRecord.tenant_id == assignment.tenant_id,
            ExceptionRecord.open.is_(True),
        ))
        assignment.help_requested = remaining is not None
    db.commit()
    return {"open": False}


@router.get("/assignments", response_model=list[TeacherAssignmentResponse])
def assignment_dashboard(
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    class_ids = teacher_class_ids(db, principal)
    assignments = db.scalars(
        select(Assignment)
        .where(
            Assignment.tenant_id == principal.user.tenant_id,
            Assignment.class_id.in_(class_ids),
            Assignment.superseded_at.is_(None),
        )
        .order_by(Assignment.delivered_at.desc())
    ).all()
    return [
        TeacherAssignmentResponse(
            id=assignment.id,
            student_id=assignment.student_id,
            lesson_id=assignment.lesson_id,
            state=assignment.state.value,
            help_requested=assignment.help_requested,
            reviewed=assignment.reviewed_at is not None,
        )
        for assignment in assignments
    ]
