from sqlalchemy import select

from app import db as db_module
from app.models import User
from test_packet_approval import login, prepare_packet


def publish_demo_source(client) -> None:
    csrf = login(client)
    packet_id, content_hash, revision, _, _ = prepare_packet()
    response = client.post(
        f"/teacher/packets/{packet_id}/approve-and-publish",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_revision_number": revision,
            "expected_hash": content_hash,
        },
    )
    assert response.status_code == 200
    with db_module.SessionLocal.begin() as db:
        source_student = db.scalar(
            select(User).where(User.username == "student.a")
        )
        source_student.username = "ada.demo"


def test_each_demo_browser_gets_fresh_persistent_student_progress(client):
    publish_demo_source(client)
    client.cookies.clear()

    entered = client.post("/auth/demo/student")
    assert entered.status_code == 200
    csrf = entered.json()["csrf_token"]
    first = client.get("/student/assignments").json()
    assert len(first) == 1
    assert first[0]["state"] == "assigned"
    detail = client.get(f"/student/assignments/{first[0]['id']}").json()
    assert detail["completed_step_ids"] == []
    assert detail["answers"] == {}

    opened = client.post(
        f"/student/assignments/{first[0]['id']}/progress",
        headers={"X-CSRF-Token": csrf},
        json={"step_id": detail["packet"]["steps"][0]["id"], "event": "opened"},
    )
    assert opened.json()["state"] == "opened"

    same_browser = client.post("/auth/demo/student")
    assert same_browser.status_code == 200
    persisted = client.get("/student/assignments").json()
    assert persisted[0]["id"] == first[0]["id"]
    assert persisted[0]["state"] == "opened"

    client.cookies.clear()
    fresh_browser = client.post("/auth/demo/student")
    assert fresh_browser.status_code == 200
    fresh = client.get("/student/assignments").json()
    assert fresh[0]["id"] != first[0]["id"]
    assert fresh[0]["state"] == "assigned"

    client.cookies.clear()
    login(client)
    class_id = client.get("/classes").json()[0]["id"]
    roster = client.get(f"/classes/{class_id}/students").json()
    assert len(roster) == 1
