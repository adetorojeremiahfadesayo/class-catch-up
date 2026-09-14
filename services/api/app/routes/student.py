from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_csrf, require_student
from app.db import get_db
from app.models import (
    Assignment,
    AssignmentState,
    Attempt,
    Enrollment,
    ExceptionRecord,
    PacketRevision,
    PacketStatus,
    ProgressEvent,
)
from app.schemas import (
    AssignmentDetail,
    AssignmentSummary,
    AttemptCreate,
    AttemptResponse,
    HelpCreate,
    ProgressCreate,
)


router = APIRouter(prefix="/student", tags=["student"])


def student_id_for_user(db: Session, principal: Principal) -> str:
    student_id = db.scalar(
        select(Enrollment.student_id).where(
            Enrollment.tenant_id == principal.user.tenant_id,
            Enrollment.user_id == principal.user.id,
        )
    )
    if student_id is None:
        raise HTTPException(status_code=404)
    return student_id


def get_student_assignment(
    db: Session, principal: Principal, assignment_id: str
) -> tuple[Assignment, PacketRevision]:
    student_id = student_id_for_user(db, principal)
    row = db.execute(
        select(Assignment, PacketRevision)
        .join(PacketRevision, PacketRevision.id == Assignment.packet_revision_id)
        .where(
            Assignment.id == assignment_id,
            Assignment.tenant_id == principal.user.tenant_id,
            Assignment.student_id == student_id,
            Assignment.superseded_at.is_(None),
            PacketRevision.status == PacketStatus.published,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404)
    return row


def student_packet(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = {
        **payload,
        "questions": [
            {
                key: value
                for key, value in question.items()
                if key not in {"answer_key", "rationale"}
            }
            for question in payload.get("questions", [])
        ],
    }
    return sanitized


@router.get("/assignments", response_model=list[AssignmentSummary])
def list_assignments(
    principal: Principal = Depends(require_student),
    db: Session = Depends(get_db),
):
    student_id = student_id_for_user(db, principal)
    rows = db.execute(
        select(Assignment, PacketRevision)
        .join(PacketRevision, PacketRevision.id == Assignment.packet_revision_id)
        .where(
            Assignment.tenant_id == principal.user.tenant_id,
            Assignment.student_id == student_id,
            Assignment.superseded_at.is_(None),
            PacketRevision.status == PacketStatus.published,
        )
        .order_by(Assignment.delivered_at.desc())
    ).all()
    return [
        AssignmentSummary(
            id=assignment.id,
            lesson_id=assignment.lesson_id,
            state=assignment.state.value,
            delivered_at=assignment.delivered_at.isoformat(),
            help_requested=assignment.help_requested,
            title=packet.payload["title"],
        )
        for assignment, packet in rows
    ]


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
def assignment_detail(
    assignment_id: str,
    principal: Principal = Depends(require_student),
    db: Session = Depends(get_db),
):
    assignment, packet = get_student_assignment(db, principal, assignment_id)
    completed = db.scalars(select(ProgressEvent.step_id).where(
        ProgressEvent.assignment_id == assignment.id,
        ProgressEvent.tenant_id == principal.user.tenant_id,
        ProgressEvent.event == "completed",
    )).all()
    attempts = db.scalars(select(Attempt).where(
        Attempt.assignment_id == assignment.id,
        Attempt.tenant_id == principal.user.tenant_id,
    ).order_by(Attempt.created_at, Attempt.id)).all()
    return AssignmentDetail(
        id=assignment.id,
        lesson_id=assignment.lesson_id,
        state=assignment.state.value,
        delivered_at=assignment.delivered_at.isoformat(),
        help_requested=assignment.help_requested,
        packet=student_packet(packet.payload),
        completed_step_ids=sorted(set(completed)),
        answers={attempt.question_id: attempt.answer for attempt in attempts},
    )


@router.post("/assignments/{assignment_id}/progress")
def record_progress(
    assignment_id: str,
    payload: ProgressCreate,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if principal.user.role.value != "student":
        raise HTTPException(status_code=403)
    assignment, packet = get_student_assignment(db, principal, assignment_id)
    valid_step_ids = {step["id"] for step in packet.payload["steps"]}
    if payload.step_id not in valid_step_ids:
        raise HTTPException(status_code=422, detail="Unknown packet step")
    if payload.event == "submitted":
        completed = set(db.scalars(select(ProgressEvent.step_id).where(
            ProgressEvent.assignment_id == assignment.id,
            ProgressEvent.event == "completed",
        )).all())
        answered = set(db.scalars(select(Attempt.question_id).where(
            Attempt.assignment_id == assignment.id,
        )).all())
        if not valid_step_ids.issubset(completed) or not {
            question["id"] for question in packet.payload["questions"]
        }.issubset(answered):
            raise HTTPException(status_code=422, detail="Complete each step and answer each question before submitting")
    if assignment.state is AssignmentState.submitted:
        return {"state": assignment.state.value}
    db.add(
        ProgressEvent(
            tenant_id=principal.user.tenant_id,
            assignment_id=assignment.id,
            step_id=payload.step_id,
            event=payload.event,
        )
    )
    if payload.event == "opened" and assignment.state is AssignmentState.assigned:
        assignment.state = AssignmentState.opened
    elif payload.event == "completed":
        assignment.state = AssignmentState.in_progress
    elif payload.event == "submitted":
        assignment.state = AssignmentState.submitted
    db.commit()
    return {"state": assignment.state.value}


@router.post(
    "/assignments/{assignment_id}/attempts", response_model=AttemptResponse
)
def record_attempt(
    assignment_id: str,
    payload: AttemptCreate,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if principal.user.role.value != "student":
        raise HTTPException(status_code=403)
    assignment, packet = get_student_assignment(db, principal, assignment_id)
    question = next(
        (
            item
            for item in packet.payload["questions"]
            if item["id"] == payload.question_id
        ),
        None,
    )
    if question is None or payload.answer not in question["options"]:
        raise HTTPException(status_code=422, detail="Invalid question or answer")
    if assignment.state == AssignmentState.submitted:
        raise HTTPException(status_code=409, detail="Submitted answers cannot be changed")
    attempt = Attempt(
        tenant_id=principal.user.tenant_id,
        assignment_id=assignment.id,
        question_id=payload.question_id,
        answer=payload.answer,
        correctness=payload.answer == question["answer_key"],
    )
    db.add(attempt)
    if assignment.state in {AssignmentState.assigned, AssignmentState.opened}:
        assignment.state = AssignmentState.in_progress
    db.commit()
    db.refresh(attempt)
    return AttemptResponse(attempt_id=attempt.id, correctness=attempt.correctness)


@router.post("/assignments/{assignment_id}/help")
def request_help(
    assignment_id: str,
    payload: HelpCreate,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if principal.user.role.value != "student":
        raise HTTPException(status_code=403)
    assignment, packet = get_student_assignment(db, principal, assignment_id)
    valid_step_ids = {step["id"] for step in packet.payload["steps"]}
    if payload.step_id not in valid_step_ids:
        raise HTTPException(status_code=422, detail="Unknown packet step")
    if assignment.help_requested:
        existing = db.scalar(
            select(ExceptionRecord).where(
                ExceptionRecord.tenant_id == principal.user.tenant_id,
                ExceptionRecord.student_id == assignment.student_id,
                ExceptionRecord.lesson_id == assignment.lesson_id,
                ExceptionRecord.source_event_id == assignment.id,
                ExceptionRecord.open.is_(True),
            )
        )
        if existing is not None:
            return {"exception_id": existing.id, "help_requested": True}
    exception = ExceptionRecord(
        tenant_id=principal.user.tenant_id,
        class_id=assignment.class_id,
        student_id=assignment.student_id,
        lesson_id=assignment.lesson_id,
        reason=f"{payload.step_id}: {payload.message}",
        severity="medium",
        source_event_id=assignment.id,
    )
    db.add(exception)
    assignment.help_requested = True
    db.commit()
    db.refresh(exception)
    return {"exception_id": exception.id, "help_requested": True}
