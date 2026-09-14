from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_teacher, require_teacher_read
from app.db import get_db
from app.models import (
    Attendance,
    AttendanceStatus,
    Assignment,
    AuditEvent,
    CoverageStatus,
    Enrollment,
    IdempotencyReceipt,
    JobState,
    LessonOccurrence,
    MappingProposal,
    MappingStatus,
    PacketJob,
    Segment,
    Topic,
)
from app.routes.classes import get_owned_class
from app.schemas import (
    DayResponse,
    LessonOccurrenceCreate,
    LessonOccurrenceResponse,
    LessonSessionResponse,
    LessonSessionSave,
)


router = APIRouter(tags=["lessons"])


def get_owned_lesson(
    db: Session, principal: Principal, lesson_id: str
) -> LessonOccurrence:
    lesson = db.scalar(
        select(LessonOccurrence).where(
            LessonOccurrence.id == lesson_id,
            LessonOccurrence.tenant_id == principal.user.tenant_id,
        )
    )
    if lesson is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, lesson.class_id)
    return lesson


@router.post(
    "/classes/{class_id}/lesson-occurrences",
    response_model=LessonOccurrenceResponse,
    status_code=201,
)
def create_occurrence(
    class_id: str,
    payload: LessonOccurrenceCreate,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    valid_topics = set(
        db.scalars(
            select(Topic.id).where(
                Topic.tenant_id == principal.user.tenant_id,
                Topic.class_id == class_id,
                Topic.id.in_(payload.planned_topic_ids),
            )
        ).all()
    )
    if valid_topics != set(payload.planned_topic_ids):
        raise HTTPException(status_code=422, detail="Invalid planned topic")
    lesson = LessonOccurrence(
        tenant_id=principal.user.tenant_id,
        class_id=class_id,
        local_date=payload.local_date,
        period_key=payload.period_key,
        planned_topic_ids=payload.planned_topic_ids,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.get("/classes/{class_id}/day", response_model=DayResponse)
def class_day(
    class_id: str,
    date: date,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    occurrences = db.scalars(
        select(LessonOccurrence)
        .where(
            LessonOccurrence.tenant_id == principal.user.tenant_id,
            LessonOccurrence.class_id == class_id,
            LessonOccurrence.local_date == date,
        )
        .order_by(LessonOccurrence.period_key)
    ).all()
    attendance = db.scalars(select(Attendance).where(
        Attendance.tenant_id == principal.user.tenant_id,
        Attendance.lesson_id.in_([item.id for item in occurrences]),
    )).all()
    saved = {item.id: {} for item in occurrences}
    for item in attendance:
        saved[item.lesson_id][item.student_id] = item.status.value
    return DayResponse(local_date=date, occurrences=occurrences, attendance=saved)


def validate_confirmed_scope(
    db: Session,
    principal: Principal,
    lesson: LessonOccurrence,
    payload: LessonSessionSave,
) -> None:
    actual_topics = set(payload.actual_topic_ids)
    if not actual_topics or not set(payload.segment_ids):
        raise HTTPException(
            status_code=422,
            detail="Confirmed coverage requires actual topics and source segments",
        )
    if not actual_topics.issubset(set(lesson.planned_topic_ids)):
        raise HTTPException(
            status_code=422, detail="Actual topics must be within the planned scope"
        )
    if payload.coverage_status == "covered" and actual_topics != set(
        lesson.planned_topic_ids
    ):
        raise HTTPException(
            status_code=422, detail="Covered status requires all planned topics"
        )

    mappings = db.scalars(
        select(MappingProposal).where(
            MappingProposal.tenant_id == principal.user.tenant_id,
            MappingProposal.class_id == lesson.class_id,
            MappingProposal.topic_id.in_(actual_topics),
            MappingProposal.status == MappingStatus.approved,
        )
    ).all()
    allowed_segments = {
        segment_id
        for mapping in mappings
        for segment_id in mapping.approved_segment_ids
    }
    if not set(payload.segment_ids).issubset(allowed_segments):
        raise HTTPException(
            status_code=422,
            detail="Segments must come from approved mappings for actual topics",
        )


@router.put("/lessons/{lesson_id}/session", response_model=LessonSessionResponse)
def save_lesson_session(
    lesson_id: str,
    payload: LessonSessionSave,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    existing_receipt = db.scalar(
        select(IdempotencyReceipt).where(
            IdempotencyReceipt.tenant_id == principal.user.tenant_id,
            IdempotencyReceipt.actor_id == principal.user.id,
            IdempotencyReceipt.request_key == idempotency_key,
            IdempotencyReceipt.operation == "save_lesson_session",
        )
    )
    if existing_receipt:
        return LessonSessionResponse(
            **existing_receipt.response_payload, replayed=True
        )

    lesson = get_owned_lesson(db, principal, lesson_id)
    if lesson.revision != payload.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"current_revision": lesson.revision},
        )

    statuses = {item.student_id: item.status for item in payload.attendance}
    if len(statuses) != len(payload.attendance):
        raise HTTPException(status_code=422, detail="Duplicate student attendance")
    enrolled_ids = set(
        db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.tenant_id == principal.user.tenant_id,
                Enrollment.class_id == lesson.class_id,
                Enrollment.student_id.in_(statuses),
            )
        ).all()
    )
    if enrolled_ids != set(statuses):
        raise HTTPException(status_code=422, detail="Attendance includes non-enrolled student")

    confirmed = payload.coverage_status in {"covered", "partly_covered"}
    if confirmed:
        validate_confirmed_scope(db, principal, lesson, payload)
    elif payload.coverage_status == "moved":
        if not payload.moved_to_date or not payload.moved_to_period_key:
            raise HTTPException(
                status_code=422, detail="Moved lessons require a destination"
            )
        if payload.actual_topic_ids or payload.segment_ids:
            raise HTTPException(
                status_code=422, detail="Moved lessons cannot confirm taught scope"
            )
    elif payload.actual_topic_ids or payload.segment_ids:
        raise HTTPException(
            status_code=422, detail="Unconfirmed lessons cannot have actual scope"
        )

    new_revision = lesson.revision + 1
    lesson.coverage_status = CoverageStatus(payload.coverage_status)
    lesson.actual_topic_ids = payload.actual_topic_ids if confirmed else []
    lesson.segment_ids = payload.segment_ids if confirmed else []
    lesson.moved_to_date = payload.moved_to_date
    lesson.moved_to_period_key = payload.moved_to_period_key
    lesson.revision = new_revision

    for student_id, attendance_status in statuses.items():
        attendance = db.scalar(
            select(Attendance).where(
                Attendance.tenant_id == principal.user.tenant_id,
                Attendance.lesson_id == lesson.id,
                Attendance.student_id == student_id,
            )
        )
        if attendance is None:
            attendance = Attendance(
                tenant_id=principal.user.tenant_id,
                lesson_id=lesson.id,
                student_id=student_id,
                status=AttendanceStatus(attendance_status),
                revision=new_revision,
            )
            db.add(attendance)
        else:
            attendance.status = AttendanceStatus(attendance_status)
            attendance.revision = new_revision

    absent_ids = [
        student_id for student_id, value in statuses.items() if value == "absent"
    ]
    present_ids = {
        student_id for student_id, value in statuses.items() if value == "present"
    }
    withdrawn_assignments = db.scalars(
        select(Assignment).where(
            Assignment.tenant_id == principal.user.tenant_id,
            Assignment.lesson_id == lesson.id,
            Assignment.student_id.in_(present_ids),
            Assignment.superseded_at.is_(None),
        )
    ).all()
    for assignment in withdrawn_assignments:
        assignment.superseded_at = datetime.now(UTC)

    stale_jobs = db.scalars(
        select(PacketJob).where(
            PacketJob.tenant_id == principal.user.tenant_id,
            PacketJob.lesson_id == lesson.id,
            PacketJob.lesson_revision < new_revision,
            PacketJob.state.in_(
                [JobState.queued, JobState.retry_wait, JobState.running]
            ),
        )
    ).all()
    for stale_job in stale_jobs:
        stale_job.state = JobState.cancelled
        stale_job.error_code = "superseded_lesson_revision"

    job = None
    blocked_reason = None
    if confirmed and absent_ids:
        job_key = f"{lesson.id}:{new_revision}:packet-v1"
        job = PacketJob(
            tenant_id=principal.user.tenant_id,
            lesson_id=lesson.id,
            lesson_revision=new_revision,
            state=JobState.queued,
            idempotency_key=job_key,
        )
        db.add(job)
        db.flush()
    elif absent_ids:
        blocked_reason = "Coverage must be confirmed before packet generation"

    response_payload = {
        "lesson_id": lesson.id,
        "revision": new_revision,
        "job_id": job.id if job else None,
        "job_state": job.state.value if job else None,
        "blocked_reason": blocked_reason,
    }
    db.add(
        IdempotencyReceipt(
            tenant_id=principal.user.tenant_id,
            actor_id=principal.user.id,
            request_key=idempotency_key,
            operation="save_lesson_session",
            response_payload=response_payload,
        )
    )
    db.add(
        AuditEvent(
            tenant_id=principal.user.tenant_id,
            class_id=lesson.class_id,
            actor_id=principal.user.id,
            event_type="lesson_session_saved",
            source_event_id=job.id if job else None,
            payload={
                "lesson_id": lesson.id,
                "revision": new_revision,
                "coverage_status": payload.coverage_status,
                "absent_count": len(absent_ids),
                "job_created": job is not None,
                "assignments_withdrawn": len(withdrawn_assignments),
            },
        )
    )
    db.commit()
    return LessonSessionResponse(**response_payload)
