from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.main import create_app
from app.models import Assignment, Attempt, ProgressEvent
from test_packet_approval import prepare_packet


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_cross_role_student_journey_persists_and_hides_answer_keys(
    client: TestClient,
) -> None:
    teacher_csrf = login(client, "teacher.a", "teacher-a-password")
    packet_id, content_hash, revision, _, _ = prepare_packet()
    published = client.post(
        f"/teacher/packets/{packet_id}/approve-and-publish",
        headers={"X-CSRF-Token": teacher_csrf},
        json={
            "expected_revision_number": revision,
            "expected_hash": content_hash,
        },
    )
    assert published.status_code == 200

    client.cookies.clear()
    student_csrf = login(client, "student.a", "student-a-password")
    assignments = client.get("/student/assignments")
    assert assignments.status_code == 200
    assignment_id = assignments.json()[0]["id"]
    detail = client.get(f"/student/assignments/{assignment_id}")
    assert detail.status_code == 200
    packet = detail.json()["packet"]
    assert "answer_key" not in packet["questions"][0]
    assert "rationale" not in packet["questions"][0]

    segment_id = packet["steps"][0]["blocks"][0]["citations"][0]["segment_id"]
    assert client.get(f"/sources/{segment_id}").status_code == 200
    assert client.get("/student/assignments/not-an-assignment").status_code == 404

    progress = client.post(
        f"/student/assignments/{assignment_id}/progress",
        headers={"X-CSRF-Token": student_csrf},
        json={"step_id": "read-1", "event": "completed"},
    )
    assert progress.status_code == 200
    assert progress.json()["state"] == "in_progress"

    attempt = client.post(
        f"/student/assignments/{assignment_id}/attempts",
        headers={"X-CSRF-Token": student_csrf},
        json={"question_id": "q-1", "answer": "a"},
    )
    assert attempt.status_code == 200
    assert attempt.json()["correctness"] is True

    help_response = client.post(
        f"/student/assignments/{assignment_id}/help",
        headers={"X-CSRF-Token": student_csrf},
        json={"step_id": "worked-1", "message": "I need help with this step."},
    )
    assert help_response.status_code == 200

    with TestClient(create_app()) as reloaded_client:
        login(reloaded_client, "teacher.a", "teacher-a-password")
        dashboard = reloaded_client.get("/teacher/assignments")
        exceptions = reloaded_client.get("/teacher/exceptions")
        assert dashboard.status_code == 200
        assert dashboard.json()[0]["state"] == "in_progress"
        assert dashboard.json()[0]["help_requested"] is True
        assert exceptions.status_code == 200
        assert "worked-1" in exceptions.json()[0]["reason"]

    with db_module.SessionLocal() as db:
        assignment = db.get(Assignment, assignment_id)
        assert assignment.help_requested is True
        assert len(db.scalars(select(ProgressEvent)).all()) == 1
        assert len(db.scalars(select(Attempt)).all()) == 1
