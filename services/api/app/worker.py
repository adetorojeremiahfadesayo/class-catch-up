import signal
import time
import multiprocessing
from datetime import UTC, datetime, timedelta
from sqlalchemy import update

from app.agent_runtime import run_packet_job
from app.db import SessionLocal
from app.jobs import claim_next_job
from app.jobs import mark_job_failed
from app.models import AgentRun, PacketJob, JobState, RunOutcome


stopping = False


def execute_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(PacketJob, job_id)
        if job is not None:
            run_packet_job(db, job)


def supervise_job(job_id: str, attempt: int, deadline_seconds: int = 300) -> None:
    """Renew the lease while a bounded child process owns this attempt."""
    process = multiprocessing.get_context("spawn").Process(target=execute_job, args=(job_id,))
    process.start()
    deadline = time.monotonic() + deadline_seconds
    failure = None
    try:
        while process.is_alive():
            process.join(timeout=10)
            if not process.is_alive():
                break
            if stopping or time.monotonic() >= deadline:
                failure = "worker_stopped" if stopping else "job_deadline_exceeded"
                break
            with SessionLocal.begin() as db:
                renewed = db.execute(update(PacketJob).where(
                    PacketJob.id == job_id,
                    PacketJob.state == JobState.running,
                    PacketJob.attempts == attempt,
                ).values(lease_until=datetime.now(UTC) + timedelta(seconds=120)))
                if renewed.rowcount != 1:
                    break
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
    with SessionLocal() as db:
        job = db.get(PacketJob, job_id)
        if job is not None and job.state == JobState.running and job.attempts == attempt:
            error_code = failure or "worker_exited_without_result"
            db.execute(
                update(AgentRun)
                .where(
                    AgentRun.job_id == job_id,
                    AgentRun.outcome == RunOutcome.running,
                )
                .values(
                    outcome=RunOutcome.failed,
                    error_code=error_code,
                    completed_at=datetime.now(UTC),
                )
            )
            mark_job_failed(db, job, error_code)


def request_stop(_signal_number, _frame) -> None:
    global stopping
    stopping = True


def main() -> None:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    print("Packet worker started")
    while not stopping:
        with SessionLocal() as db:
            job = claim_next_job(db)
            if job is not None:
                job_id, attempt = job.id, job.attempts
                db.close()
                supervise_job(job_id, attempt)
                continue
        time.sleep(2)
    print("Packet worker stopped")


if __name__ == "__main__":
    main()
