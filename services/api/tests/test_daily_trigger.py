from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.models import (
    Enrollment,
    ExtractionStatus,
    MappingProposal,
    MappingStatus,
    Material,
    PacketJob,
    SchoolClass,
    Segment,
    Topic,
    new_id,
)


def login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"username": "teacher.a", "password": "teacher-a-password"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def prepare_scope() -> tuple[str, list[str], list[str], str]:
    with db_module.SessionLocal.begin() as db:
        school_class = db.scalar(select(SchoolClass).where(SchoolClass.name == "Class A"))
        students = db.scalars(
            select(Enrollment).where(Enrollment.class_id == school_class.id)
        ).all()
        topic_a = Topic(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            title="Equivalent fractions",
            objectives=["Recognize equivalent fractions"],
        )
        topic_b = Topic(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            title="Adding fractions",
            objectives=["Add like denominators"],
        )
        db.add_all([topic_a, topic_b])
        db.flush()
        material = Material(
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            filename="fractions.txt",
            media_type="text/plain",
            content_hash="b" * 64,
            storage_key="test/fractions.txt",
            version=1,
            extraction_status=ExtractionStatus.ready,
        )
        db.add(material)
        db.flush()
        segment_a = Segment(
            id=new_id(),
            tenant_id=school_class.tenant_id,
            class_id=school_class.id,
            material_id=material.id,
            position=1,
            page_1_based=1,
            text_section=None,
            text="Equivalent fractions name the same amount.",
            content_hash="a" * 64,
        )
        db.add(segment_a)
        db.flush()
        db.add(
            MappingProposal(
                tenant_id=school_class.tenant_id,
                class_id=school_class.id,
                topic_id=topic_a.id,
                suggested_segment_ids=[segment_a.id],
                approved_segment_ids=[segment_a.id],
                unmatched=False,
                proposal_method="teacher_test_fixture",
                status=MappingStatus.approved,
            )
        )
        return (
            school_class.id,
            [topic_a.id, topic_b.id],
            [segment_a.id],
            students[0].student_id,
        )


def test_partial_save_is_idempotent_and_excludes_untaught_topic(
    client: TestClient,
) -> None:
    csrf = login(client)
    class_id, topic_ids, segment_ids, student_id = prepare_scope()
    occurrence = client.post(
        f"/classes/{class_id}/lesson-occurrences",
        headers={"X-CSRF-Token": csrf},
        json={
            "local_date": "2026-09-12",
            "period_key": "P1",
            "planned_topic_ids": topic_ids,
        },
    )
    assert occurrence.status_code == 201
    lesson_id = occurrence.json()["id"]
    payload = {
        "expected_revision": 0,
        "coverage_status": "partly_covered",
        "actual_topic_ids": [topic_ids[0]],
        "segment_ids": segment_ids,
        "attendance": [{"student_id": student_id, "status": "absent"}],
    }
    first = client.put(
        f"/lessons/{lesson_id}/session",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "daily-save-001"},
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["job_state"] == "queued"

    replay = client.put(
        f"/lessons/{lesson_id}/session",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "daily-save-001"},
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["job_id"] == first.json()["job_id"]

    day = client.get(f"/classes/{class_id}/day?date=2026-09-12").json()
    assert day["occurrences"][0]["actual_topic_ids"] == [topic_ids[0]]
    with db_module.SessionLocal() as db:
        assert len(db.scalars(select(PacketJob)).all()) == 1


def test_unconfirmed_absence_is_visible_but_creates_no_job(client: TestClient) -> None:
    csrf = login(client)
    class_id, topic_ids, _, student_id = prepare_scope()
    occurrence = client.post(
        f"/classes/{class_id}/lesson-occurrences",
        headers={"X-CSRF-Token": csrf},
        json={
            "local_date": "2026-09-12",
            "period_key": "P2",
            "planned_topic_ids": topic_ids,
        },
    ).json()
    response = client.put(
        f"/lessons/{occurrence['id']}/session",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "daily-save-002"},
        json={
            "expected_revision": 0,
            "coverage_status": "not_yet_confirmed",
            "actual_topic_ids": [],
            "segment_ids": [],
            "attendance": [{"student_id": student_id, "status": "absent"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["job_id"] is None
    assert "Coverage must be confirmed" in response.json()["blocked_reason"]
