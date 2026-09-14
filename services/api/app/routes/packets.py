from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Principal, require_teacher, require_teacher_read
from app.db import get_db
from app.models import (
    JobState,
    LessonOccurrence,
    PacketJob,
    PacketRevision,
    PacketStatus,
)
from app.packets import publish_packet, save_packet_draft
from app.routes.classes import get_owned_class
from app.schemas import (
    JobResponse,
    PacketApprovalRequest,
    PacketEditRequest,
    PacketPublicationResponse,
    PacketResponse,
)


router = APIRouter(tags=["packets"])


def packet_response(packet: PacketRevision) -> PacketResponse:
    return PacketResponse(
        id=packet.id,
        lesson_id=packet.lesson_id,
        lesson_revision=packet.lesson_revision,
        revision_number=packet.revision_number,
        parent_id=packet.parent_id,
        payload=packet.payload,
        validation_results=packet.validation_results,
        status=packet.status.value,
        content_hash=packet.content_hash,
        approved_hash=packet.approved_hash,
        generation_source=(
            "strands_run" if packet.generation_run_id else "fixture_or_teacher_edit"
        ),
    )


def get_owned_packet(
    db: Session, principal: Principal, packet_id: str
) -> PacketRevision:
    packet = db.scalar(
        select(PacketRevision).where(
            PacketRevision.id == packet_id,
            PacketRevision.tenant_id == principal.user.tenant_id,
        )
    )
    if packet is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, packet.class_id)
    return packet


@router.get("/teacher/packets", response_model=list[PacketResponse])
def list_packets(
    class_id: str,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    get_owned_class(db, principal, class_id)
    packets = db.scalars(
        select(PacketRevision)
        .where(
            PacketRevision.tenant_id == principal.user.tenant_id,
            PacketRevision.class_id == class_id,
        )
        .order_by(PacketRevision.created_at.desc())
    ).all()
    return [packet_response(packet) for packet in packets]


@router.get("/teacher/packets/{packet_id}", response_model=PacketResponse)
def get_packet(
    packet_id: str,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    return packet_response(get_owned_packet(db, principal, packet_id))


@router.patch("/teacher/packets/{packet_id}", response_model=PacketResponse)
def edit_packet(
    packet_id: str,
    payload: PacketEditRequest,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    packet = get_owned_packet(db, principal, packet_id)
    if (
        packet.revision_number != payload.expected_revision_number
        or packet.content_hash != payload.expected_hash
    ):
        raise HTTPException(status_code=409, detail="Packet revision or hash is stale")
    lesson = db.scalar(
        select(LessonOccurrence).where(
            LessonOccurrence.id == packet.lesson_id,
            LessonOccurrence.tenant_id == packet.tenant_id,
        )
    )
    if lesson is None:
        raise HTTPException(status_code=404)
    new_packet = save_packet_draft(
        db,
        lesson,
        payload.candidate,
        expected_lesson_revision=packet.lesson_revision,
        generation_run_id=None,
    )
    new_packet.parent_id = packet.id
    if packet.status in {PacketStatus.needs_review, PacketStatus.needs_revision}:
        packet.status = PacketStatus.superseded
    db.commit()
    db.refresh(new_packet)
    return packet_response(new_packet)


@router.post(
    "/teacher/packets/{packet_id}/approve-and-publish",
    response_model=PacketPublicationResponse,
)
def approve_and_publish(
    packet_id: str,
    payload: PacketApprovalRequest,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    packet = get_owned_packet(db, principal, packet_id)
    assignments = publish_packet(
        db,
        packet,
        reviewer_id=principal.user.id,
        expected_revision_number=payload.expected_revision_number,
        expected_hash=payload.expected_hash,
    )
    return PacketPublicationResponse(
        packet_id=packet.id, status="published", assignment_count=len(assignments)
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_teacher_read),
    db: Session = Depends(get_db),
):
    job = db.scalar(
        select(PacketJob).where(
            PacketJob.id == job_id,
            PacketJob.tenant_id == principal.user.tenant_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404)
    lesson = db.scalar(
        select(LessonOccurrence).where(
            LessonOccurrence.id == job.lesson_id,
            LessonOccurrence.tenant_id == principal.user.tenant_id,
        )
    )
    if lesson is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, lesson.class_id)
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobResponse, status_code=201)
def retry_job(
    job_id: str,
    principal: Principal = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    failed = db.scalar(
        select(PacketJob).where(
            PacketJob.id == job_id,
            PacketJob.tenant_id == principal.user.tenant_id,
        )
    )
    if failed is None:
        raise HTTPException(status_code=404)
    if failed.state is not JobState.failed:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    lesson = db.scalar(
        select(LessonOccurrence).where(
            LessonOccurrence.id == failed.lesson_id,
            LessonOccurrence.tenant_id == failed.tenant_id,
        )
    )
    if lesson is None:
        raise HTTPException(status_code=404)
    get_owned_class(db, principal, lesson.class_id)
    retry_number = (
        db.scalar(
            select(func.count(PacketJob.id)).where(
                PacketJob.tenant_id == failed.tenant_id,
                PacketJob.idempotency_key.like(
                    f"{failed.idempotency_key}:manual-retry:%"
                ),
            )
        )
        or 0
    ) + 1
    retry = PacketJob(
        tenant_id=failed.tenant_id,
        lesson_id=failed.lesson_id,
        lesson_revision=failed.lesson_revision,
        state=JobState.queued,
        idempotency_key=(
            f"{failed.idempotency_key}:manual-retry:{retry_number}"
        ),
    )
    db.add(retry)
    db.commit()
    db.refresh(retry)
    return retry
