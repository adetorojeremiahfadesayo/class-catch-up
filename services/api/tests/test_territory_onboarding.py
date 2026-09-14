from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.models import SchoolClass, User


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def class_id(name: str) -> str:
    with db_module.SessionLocal() as db:
        return db.scalar(select(SchoolClass.id).where(SchoolClass.name == name))


def test_teacher_completes_us_onboarding_and_student_sees_introduction(
    client: TestClient,
) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    initial = client.get("/teacher/onboarding")
    assert initial.status_code == 200
    assert initial.json()["completed"] is False
    assert {
        option["id"] for option in initial.json()["education_systems"]
    } == {"united_states_high_school", "england_wales_secondary"}

    response = client.put(
        "/teacher/onboarding",
        headers={"X-CSRF-Token": csrf},
        json={
            "display_name": "Dr. Jordan",
            "introduction": (
                "I teach mathematics and will help you reconnect with each lesson."
            ),
            "class_id": class_id("Class A"),
            "education_system": "united_states_high_school",
            "level_label": "Grade 10",
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 200
    assert response.json()["completed"] is True
    configured_class = response.json()["classes"][0]
    assert configured_class["education_system"] == "united_states_high_school"
    assert configured_class["level_label"] == "Grade 10"

    client.cookies.clear()
    login(client, "student.a", "student-a-password")
    student_context = client.get("/student/context")
    assert student_context.status_code == 200
    assert student_context.json()["teacher_display_name"] == "Dr. Jordan"
    assert student_context.json()["teacher_introduction"].startswith(
        "I teach mathematics"
    )
    assert student_context.json()["period_label"] == "Period"


def test_onboarding_rejects_level_from_another_system(client: TestClient) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    response = client.put(
        "/teacher/onboarding",
        headers={"X-CSRF-Token": csrf},
        json={
            "display_name": "Teacher A",
            "introduction": "Welcome to our mathematics class this school year.",
            "class_id": class_id("Class A"),
            "education_system": "england_wales_secondary",
            "level_label": "Grade 10",
            "timezone": "Europe/London",
        },
    )
    assert response.status_code == 422


def test_teacher_cannot_configure_another_tenants_class(client: TestClient) -> None:
    csrf = login(client, "teacher.a", "teacher-a-password")
    response = client.put(
        "/teacher/onboarding",
        headers={"X-CSRF-Token": csrf},
        json={
            "display_name": "Teacher A",
            "introduction": "Welcome to our mathematics class this school year.",
            "class_id": class_id("Class B"),
            "education_system": "england_wales_secondary",
            "level_label": "Year 10",
            "timezone": "Europe/London",
        },
    )
    assert response.status_code == 404
