from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import JobState, PacketJob


MAX_JOB_ATTEMPTS = 3


def claim_next_job(db: Session, lease_seconds: int = 120) -> PacketJob | None:
    now = datetime.now(UTC)
    exhausted = db.scalars(select(PacketJob).where(
        PacketJob.state == JobState.running,
        PacketJob.lease_until < now,
        PacketJob.attempts >= MAX_JOB_ATTEMPTS,
    ).with_for_update(skip_locked=True)).all()
    for expired in exhausted:
        expired.state = JobState.failed
        expired.error_code = "worker_lease_expired_attempts_exhausted"
        expired.lease_until = None
    db.flush()
    job = db.scalar(
        select(PacketJob)
        .where(
            or_(
                PacketJob.state == JobState.queued,
                (
                    (PacketJob.state == JobState.retry_wait)
                    & (PacketJob.next_attempt_at <= now)
                ),
                (
                    (PacketJob.state == JobState.running)
                    & (PacketJob.lease_until < now)
                ),
            ),
            PacketJob.attempts < MAX_JOB_ATTEMPTS,
        )
        .order_by(PacketJob.created_at)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.commit()
        return None
    job.state = JobState.running
    job.attempts += 1
    job.lease_until = now + timedelta(seconds=lease_seconds)
    job.next_attempt_at = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(db: Session, job: PacketJob, error_code: str) -> None:
    job.error_code = error_code
    job.lease_until = None
    if job.attempts >= MAX_JOB_ATTEMPTS:
        job.state = JobState.failed
    else:
        job.state = JobState.retry_wait
        job.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=30 * (2 ** (job.attempts - 1))
        )
    db.commit()
