from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app import db as db_module
from app.models import LessonOccurrence, PacketRevision, PacketJob, JobState
from app.jobs import claim_next_job
from app.packets import validate_packet_candidate
from test_packet_approval import prepare_packet, login


def publish(client):
    csrf = login(client)
    packet_id, content_hash, revision, _, _ = prepare_packet()
    response = client.post(f"/teacher/packets/{packet_id}/approve-and-publish", headers={"X-CSRF-Token": csrf}, json={"expected_revision_number": revision, "expected_hash": content_hash})
    assert response.status_code == 200
    return packet_id


def student_login(client):
    client.cookies.clear()
    response = client.post("/auth/login", json={"username": "student.a", "password": "student-a-password"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_saved_attendance_and_planning_are_readable_and_scoped(client):
    login(client)
    packet_id, *_ = prepare_packet()
    with db_module.SessionLocal() as db:
        packet = db.get(PacketRevision, packet_id)
        class_id, lesson_id = packet.class_id, packet.lesson_id
    day = client.get(f"/classes/{class_id}/day?date=2026-09-12").json()
    assert list(day["attendance"][lesson_id].values()) == ["absent"]
    plan = client.get(f"/classes/{class_id}/planning").json()
    assert plan["topics"][0]["title"] == "Equivalent fractions"
    assert "page 1" in plan["segments"][0]["label"]
    student_login(client)
    assert client.get(f"/classes/{class_id}/planning").status_code == 403


def test_progress_restores_and_submission_requires_complete_work(client):
    publish(client)
    headers = student_login(client)
    assignment_id = client.get("/student/assignments").json()[0]["id"]
    url = f"/student/assignments/{assignment_id}"
    packet = client.get(url).json()["packet"]
    submitted = {"step_id": packet["steps"][0]["id"], "event": "submitted"}
    assert client.post(url + "/progress", headers=headers, json=submitted).status_code == 422
    for step in packet["steps"]:
        assert client.post(url + "/progress", headers=headers, json={"step_id": step["id"], "event": "completed"}).status_code == 200
    for question in packet["questions"]:
        assert client.post(url + "/attempts", headers=headers, json={"question_id": question["id"], "answer": "a"}).status_code == 200
    restored = client.get(url).json()
    assert len(restored["completed_step_ids"]) == 4
    assert len(restored["answers"]) == 3
    assert "answer_key" not in restored["packet"]["questions"][0]
    assert client.post(url + "/progress", headers=headers, json=submitted).json()["state"] == "submitted"
    assert client.post(url + "/progress", headers=headers, json={"step_id": "read-1", "event": "completed"}).json()["state"] == "submitted"
    assert client.post(url + "/attempts", headers=headers, json={"question_id": "q-1", "answer": "b"}).status_code == 409


def test_help_can_be_requested_after_resolution(client):
    publish(client)
    headers = student_login(client)
    assignment_id = client.get("/student/assignments").json()[0]["id"]
    url = f"/student/assignments/{assignment_id}/help"
    payload = {"step_id": "read-1", "message": "Please explain this"}
    first = client.post(url, headers=headers, json=payload).json()["exception_id"]
    client.cookies.clear()
    csrf = login(client)
    assert client.post(f"/teacher/exceptions/{first}/resolve", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert not client.get("/teacher/assignments").json()[0]["help_requested"]
    headers = student_login(client)
    second = client.post(url, headers=headers, json=payload)
    assert second.status_code == 200
    assert second.json()["exception_id"] != first


def test_citation_rejects_wrong_page_and_fabricated_direct_excerpt(client):
    packet_id, *_ = prepare_packet()
    with db_module.SessionLocal() as db:
        packet = db.get(PacketRevision, packet_id)
        lesson = db.get(LessonOccurrence, packet.lesson_id)
        candidate = packet.payload
        candidate["steps"][0]["blocks"][0]["citations"][0]["page_or_section"] = "page 99"
        candidate["steps"][0]["blocks"][0]["text"] = "A fabricated quote"
        _, result = validate_packet_candidate(db, lesson, candidate)
        assert not result["valid"]
        assert any("page or section" in error for error in result["errors"])
        assert any("Direct excerpt" in error for error in result["errors"])


def test_expired_final_attempt_becomes_failed(client):
    packet_id, *_ = prepare_packet()
    with db_module.SessionLocal.begin() as db:
        packet = db.get(PacketRevision, packet_id)
        job = PacketJob(tenant_id=packet.tenant_id, lesson_id=packet.lesson_id, lesson_revision=1, state=JobState.running, attempts=3, lease_until=datetime.now(UTC)-timedelta(seconds=5), idempotency_key="expired-final")
        db.add(job)
    with db_module.SessionLocal() as db:
        assert claim_next_job(db) is None
        job = db.scalar(select(PacketJob).where(PacketJob.idempotency_key == "expired-final"))
        assert job.state == JobState.failed


def test_supervisor_terminates_overdue_child_and_records_failure(client, monkeypatch):
    from app import worker
    packet_id, *_ = prepare_packet()
    with db_module.SessionLocal.begin() as db:
        packet = db.get(PacketRevision, packet_id)
        job = PacketJob(tenant_id=packet.tenant_id, lesson_id=packet.lesson_id, lesson_revision=1, state=JobState.running, attempts=1, lease_until=datetime.now(UTC)+timedelta(seconds=120), idempotency_key="supervisor-timeout")
        db.add(job)
        db.flush()
        job_id = job.id

    class OverdueChild:
        alive = True
        def start(self): pass
        def join(self, timeout=None): pass
        def is_alive(self): return self.alive
        def terminate(self): self.alive = False

    child = OverdueChild()
    class Context:
        def Process(self, **kwargs): return child
    monkeypatch.setattr(worker.multiprocessing, "get_context", lambda _: Context())
    monkeypatch.setattr(worker, "SessionLocal", db_module.SessionLocal)
    worker.supervise_job(job_id, attempt=1, deadline_seconds=0)
    assert not child.alive
    with db_module.SessionLocal() as db:
        job = db.get(PacketJob, job_id)
        assert job.state == JobState.retry_wait
        assert job.error_code == "job_deadline_exceeded"
