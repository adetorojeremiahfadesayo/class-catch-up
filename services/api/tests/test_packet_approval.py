from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.agent_runtime import run_packet_job
from app.models import (
    AgentRun,
    Assignment,
    Attendance,
    AttendanceStatus,
    Enrollment,
    ExtractionStatus,
    JobState,
    LessonOccurrence,
    Material,
    MappingProposal,
    MappingStatus,
    PacketJob,
    PacketRevision,
    PacketStatus,
    SchoolClass,
    Segment,
    Topic,
    new_id,
)
from app.packets import save_packet_draft


EXCERPT = "Equivalent fractions name the same amount."


def login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"username": "teacher.a", "password": "teacher-a-password"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def packet_candidate(segment_id: str) -> dict:
    citation = {
        "segment_id": segment_id,
        "page_or_section": "page 1",
        "supporting_excerpt": EXCERPT,
    }
    return {
        "title": "Catch up: Equivalent fractions",
        "objectives": ["Recognize equivalent fractions"],
        "estimated_minutes": 15,
        "steps": [
            {
                "id": "read-1",
                "kind": "read",
                "title": "Read",
                "blocks": [
                    {
                        "text": EXCERPT,
                        "content_kind": "direct_excerpt",
                        "citations": [citation],
                    }
                ],
            },
            {
                "id": "explain-1",
                "kind": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "text": "Different fraction names can represent one amount.",
                        "content_kind": "generated_from_source",
                        "citations": [citation],
                    }
                ],
            },
            {
                "id": "worked-1",
                "kind": "worked_example",
                "title": "Worked example",
                "blocks": [
                    {
                        "text": "For example, one half and two quarters are equivalent.",
                        "content_kind": "generated_from_source",
                        "citations": [citation],
                    }
                ],
            },
            {
                "id": "practice-1",
                "kind": "practice",
                "title": "Practice",
                "blocks": [
                    {
                        "text": "Use the source idea to compare fraction pairs.",
                        "content_kind": "generated_from_source",
                        "citations": [citation],
                    }
                ],
            },
        ],
        "questions": [
            {
                "id": f"q-{number}",
                "prompt": "Which statement matches the source?",
                "options": {
                    "a": "Equivalent fractions can name the same amount.",
                    "b": "Equivalent fractions must use identical numbers.",
                },
                "answer_key": "a",
                "rationale": "The source states that they name the same amount.",
                "citations": [citation],
            }
            for number in range(1, 4)
        ],
    }


def prepare_packet() -> tuple[str, str, int, str, str]:
    with db_module.SessionLocal.begin() as db:
        school_class = db.scalar(select(SchoolClass).where(SchoolClass.name == "Class A"))
        enrollment = db.scalar(
            select(Enrollment).where(Enrollment.class_id == school_class.id)
        )
        topic = Topic(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            title="Equivalent fractions",
            objectives=["Recognize equivalent fractions"],
        )
        material = Material(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            filename="fractions.pdf",
            media_type="application/pdf",
            content_hash="c" * 64,
            storage_key="test/fractions.pdf",
            version=1,
            extraction_status=ExtractionStatus.ready,
        )
        db.add_all([topic, material])
        db.flush()
        segment = Segment(
            id=new_id(),
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            material_id=material.id,
            position=1,
            page_1_based=1,
            text_section=None,
            text=EXCERPT,
            content_hash="d" * 64,
        )
        db.add(segment)
        db.flush()
        db.add(
            MappingProposal(
                tenant_id=school_class.tenant_id,
                class_id=school_class.id,
                topic_id=topic.id,
                suggested_segment_ids=[segment.id],
                approved_segment_ids=[segment.id],
                unmatched=False,
                proposal_method="teacher_test_fixture",
                status=MappingStatus.approved,
            )
        )
        lesson = LessonOccurrence(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            local_date=date(2026, 9, 12),
            period_key="P1",
            planned_topic_ids=[topic.id],
            actual_topic_ids=[topic.id],
            segment_ids=[segment.id],
            coverage_status="covered",
            revision=1,
        )
        db.add(lesson)
        db.flush()
        db.add(
            Attendance(
                tenant_id=school_class.tenant_id,
                lesson_id=lesson.id,
                student_id=enrollment.student_id,
                status=AttendanceStatus.absent,
                revision=1,
            )
        )
        packet = save_packet_draft(
            db,
            lesson,
            packet_candidate(segment.id),
            expected_lesson_revision=1,
            generation_run_id=None,
        )
        db.flush()
        return (
            packet.id,
            packet.content_hash,
            packet.revision_number,
            enrollment.student_id,
            lesson.id,
        )


def test_stale_hash_rejected_then_exact_revision_published(
    client: TestClient,
) -> None:
    csrf = login(client)
    packet_id, content_hash, revision, student_id, _ = prepare_packet()
    stale = client.post(
        f"/teacher/packets/{packet_id}/approve-and-publish",
        headers={"X-CSRF-Token": csrf},
        json={"expected_revision_number": revision, "expected_hash": "0" * 64},
    )
    assert stale.status_code == 409

    published = client.post(
        f"/teacher/packets/{packet_id}/approve-and-publish",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_revision_number": revision,
            "expected_hash": content_hash,
        },
    )
    assert published.status_code == 200
    assert published.json()["assignment_count"] == 1
    with db_module.SessionLocal() as db:
        assignment = db.scalar(select(Assignment))
        packet = db.get(PacketRevision, packet_id)
        lesson = db.get(LessonOccurrence, packet.lesson_id)
        assert assignment.student_id == student_id
        assert packet.status is PacketStatus.published
        assert packet.approved_hash == content_hash
        actual_topic_ids = lesson.actual_topic_ids
        segment_ids = lesson.segment_ids
        lesson_id = lesson.id

    correction = client.put(
        f"/lessons/{lesson_id}/session",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "attendance-correction-001",
        },
        json={
            "expected_revision": 1,
            "coverage_status": "covered",
            "actual_topic_ids": actual_topic_ids,
            "segment_ids": segment_ids,
            "attendance": [{"student_id": student_id, "status": "present"}],
        },
    )
    assert correction.status_code == 200
    assert correction.json()["job_id"] is None
    with db_module.SessionLocal() as db:
        assignment = db.scalar(select(Assignment))
        assert assignment.superseded_at is not None


def test_invalid_citation_creates_non_publishable_revision(client: TestClient) -> None:
    csrf = login(client)
    packet_id, _, _, _, _ = prepare_packet()
    with db_module.SessionLocal.begin() as db:
        packet = db.get(PacketRevision, packet_id)
        lesson = db.get(LessonOccurrence, packet.lesson_id)
        invalid = packet_candidate("outside-scope")
        invalid_packet = save_packet_draft(
            db,
            lesson,
            invalid,
            expected_lesson_revision=lesson.revision,
            generation_run_id=None,
        )
        invalid_id = invalid_packet.id
        invalid_hash = invalid_packet.content_hash
        invalid_revision = invalid_packet.revision_number
        assert invalid_packet.status is PacketStatus.needs_revision

    response = client.post(
        f"/teacher/packets/{invalid_id}/approve-and-publish",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_revision_number": invalid_revision,
            "expected_hash": invalid_hash,
        },
    )
    assert response.status_code == 409


def test_unconfigured_provider_records_failure_not_success(client: TestClient) -> None:
    _, _, _, _, lesson_id = prepare_packet()
    with db_module.SessionLocal.begin() as db:
        lesson = db.get(LessonOccurrence, lesson_id)
        job = PacketJob(
            tenant_id=lesson.tenant_id,
            lesson_id=lesson.id,
            lesson_revision=lesson.revision,
            state=JobState.running,
            attempts=1,
            idempotency_key=f"{lesson.id}:provider-test",
        )
        db.add(job)
        db.flush()
        job_id = job.id

    with db_module.SessionLocal() as db:
        job = db.get(PacketJob, job_id)
        assert run_packet_job(db, job) is None

    with db_module.SessionLocal() as db:
        job = db.get(PacketJob, job_id)
        run = db.scalar(select(AgentRun).where(AgentRun.job_id == job_id))
        assert job.state is JobState.retry_wait
        assert job.error_code == "provider_not_configured"
        assert run.outcome.value == "failed"
        assert run.error_code == "provider_not_configured"
