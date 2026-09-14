from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    AssignmentState,
    Attendance,
    AttendanceStatus,
    AuditEvent,
    Enrollment,
    LessonOccurrence,
    PacketRevision,
    PacketStatus,
    Segment,
)
from app.packet_schemas import PacketCandidate


def packet_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_packet_candidate(
    db: Session, lesson: LessonOccurrence, candidate_data: dict[str, Any]
) -> tuple[PacketCandidate | None, dict[str, Any]]:
    errors: list[str] = []
    try:
        candidate = PacketCandidate.model_validate(candidate_data)
    except ValidationError as error:
        return None, {
            "valid": False,
            "errors": [
                {
                    "location": ".".join(str(item) for item in detail["loc"]),
                    "message": detail["msg"],
                }
                for detail in error.errors()
            ],
        }

    allowed_segments = {
        segment.id: segment
        for segment in db.scalars(
            select(Segment).where(
                Segment.tenant_id == lesson.tenant_id,
                Segment.class_id == lesson.class_id,
                Segment.id.in_(lesson.segment_ids),
            )
        ).all()
    }
    if set(allowed_segments) != set(lesson.segment_ids):
        errors.append("Confirmed lesson contains unavailable source segments")

    citations = [
        citation
        for step in candidate.steps
        for block in step.blocks
        for citation in block.citations
    ] + [
        citation for question in candidate.questions for citation in question.citations
    ]
    for citation in citations:
        segment = allowed_segments.get(citation.segment_id)
        if segment is None:
            errors.append(f"Citation {citation.segment_id} is outside lesson scope")
            continue
        expected_label = f"page {segment.page_1_based}" if segment.page_1_based else segment.text_section
        if citation.page_or_section != expected_label:
            errors.append(f"Citation page or section does not match segment {segment.id}")
        normalized_excerpt = " ".join(citation.supporting_excerpt.split()).lower()
        normalized_source = " ".join(segment.text.split()).lower()
        if normalized_excerpt not in normalized_source:
            errors.append(
                f"Citation excerpt is not present in segment {citation.segment_id}"
            )

    for step in candidate.steps:
        for block in step.blocks:
            if block.content_kind == "direct_excerpt":
                text = " ".join(block.text.split()).lower()
                if not any(text in " ".join(allowed_segments[c.segment_id].text.split()).lower() for c in block.citations if c.segment_id in allowed_segments):
                    errors.append("Direct excerpt text is not present in its cited source")
    return candidate, {"valid": not errors, "errors": sorted(set(errors))}


def save_packet_draft(
    db: Session,
    lesson: LessonOccurrence,
    candidate_data: dict[str, Any],
    expected_lesson_revision: int,
    generation_run_id: str | None,
) -> PacketRevision:
    db.refresh(lesson)
    if lesson.revision != expected_lesson_revision:
        raise HTTPException(status_code=409, detail="Lesson revision changed")

    candidate, validation_results = validate_packet_candidate(
        db, lesson, candidate_data
    )
    payload = (
        candidate.model_dump(mode="json")
        if candidate is not None
        else candidate_data
    )
    material_ids = sorted(
        set(
            db.scalars(
                select(Segment.material_id).where(
                    Segment.id.in_(lesson.segment_ids),
                    Segment.tenant_id == lesson.tenant_id,
                )
            ).all()
        )
    )
    revision_number = (
        db.scalar(
            select(func.max(PacketRevision.revision_number)).where(
                PacketRevision.tenant_id == lesson.tenant_id,
                PacketRevision.lesson_id == lesson.id,
            )
        )
        or 0
    ) + 1
    packet = PacketRevision(
        tenant_id=lesson.tenant_id,
        class_id=lesson.class_id,
        lesson_id=lesson.id,
        lesson_revision=lesson.revision,
        revision_number=revision_number,
        material_version_ids=material_ids,
        payload=payload,
        validation_results=validation_results,
        status=(
            PacketStatus.needs_review
            if validation_results["valid"]
            else PacketStatus.needs_revision
        ),
        content_hash=packet_hash(payload),
        generation_run_id=generation_run_id,
    )
    db.add(packet)
    db.flush()
    return packet


def publish_packet(
    db: Session,
    packet: PacketRevision,
    reviewer_id: str,
    expected_revision_number: int,
    expected_hash: str,
) -> list[Assignment]:
    db.refresh(packet)
    if (
        packet.revision_number != expected_revision_number
        or packet.content_hash != expected_hash
    ):
        raise HTTPException(status_code=409, detail="Packet revision or hash is stale")
    if packet.status is not PacketStatus.needs_review:
        raise HTTPException(status_code=409, detail="Packet is not reviewable")
    if not packet.validation_results.get("valid"):
        raise HTTPException(status_code=422, detail="Invalid packet cannot publish")

    lesson = db.scalar(
        select(LessonOccurrence).where(
            LessonOccurrence.id == packet.lesson_id,
            LessonOccurrence.tenant_id == packet.tenant_id,
        )
    )
    if lesson is None or lesson.revision != packet.lesson_revision:
        raise HTTPException(status_code=409, detail="Lesson scope changed")

    absent_student_ids = set(
        db.scalars(
            select(Attendance.student_id).where(
                Attendance.tenant_id == packet.tenant_id,
                Attendance.lesson_id == packet.lesson_id,
                Attendance.status == AttendanceStatus.absent,
                Attendance.revision == lesson.revision,
            )
        ).all()
    )
    enrolled_student_ids = set(
        db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.tenant_id == packet.tenant_id,
                Enrollment.class_id == packet.class_id,
                Enrollment.student_id.in_(absent_student_ids),
            )
        ).all()
    )
    if not enrolled_student_ids:
        raise HTTPException(
            status_code=409, detail="No currently absent enrolled students"
        )

    assignments = []
    for student_id in sorted(enrolled_student_ids):
        active = db.scalar(
            select(Assignment).where(
                Assignment.tenant_id == packet.tenant_id,
                Assignment.lesson_id == packet.lesson_id,
                Assignment.student_id == student_id,
                Assignment.superseded_at.is_(None),
            )
        )
        if active and active.packet_revision_id == packet.id:
            assignments.append(active)
            continue
        if active:
            active.superseded_at = datetime.now(UTC)
        assignment = Assignment(
            tenant_id=packet.tenant_id,
            class_id=packet.class_id,
            student_id=student_id,
            lesson_id=packet.lesson_id,
            packet_revision_id=packet.id,
            state=AssignmentState.assigned,
        )
        db.add(assignment)
        assignments.append(assignment)

    packet.status = PacketStatus.published
    packet.reviewer_id = reviewer_id
    packet.approved_hash = expected_hash
    db.add(
        AuditEvent(
            tenant_id=packet.tenant_id,
            class_id=packet.class_id,
            actor_id=reviewer_id,
            event_type="packet_approved_and_published",
            source_event_id=packet.id,
            payload={
                "packet_revision": packet.revision_number,
                "approved_hash": expected_hash,
                "assignment_count": len(assignments),
            },
        )
    )
    db.commit()
    return assignments
