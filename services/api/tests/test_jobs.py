from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.jobs import claim_next_job, mark_job_failed
from app.models import JobState, LessonOccurrence, PacketJob, SchoolClass


def test_worker_reclaims_expired_lease_without_duplicate_job(
    client: TestClient,
) -> None:
    with db_module.SessionLocal.begin() as db:
        school_class = db.scalar(select(SchoolClass).where(SchoolClass.name == "Class A"))
        lesson = LessonOccurrence(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            local_date=date(2026, 9, 12),
            period_key="P1",
            planned_topic_ids=[],
            actual_topic_ids=[],
            segment_ids=[],
            revision=1,
        )
        db.add(lesson)
        db.flush()
        job = PacketJob(
            tenant_id=school_class.tenant_id,
            lesson_id=lesson.id,
            lesson_revision=1,
            state=JobState.running,
            attempts=1,
            lease_until=datetime.now(UTC) - timedelta(seconds=1),
            idempotency_key=f"{lesson.id}:1:packet-v1",
        )
        db.add(job)
        db.flush()
        job_id = job.id

    with db_module.SessionLocal() as db:
        claimed = claim_next_job(db)
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.attempts == 2
        assert claimed.state is JobState.running
        mark_job_failed(db, claimed, "provider_timeout")

    with db_module.SessionLocal() as db:
        jobs = db.scalars(select(PacketJob)).all()
        assert len(jobs) == 1
        assert jobs[0].state is JobState.retry_wait
        assert jobs[0].error_code == "provider_timeout"
