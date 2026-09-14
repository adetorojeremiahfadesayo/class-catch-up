from fastapi.testclient import TestClient


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_teacher_requires_csrf_for_writes(client: TestClient) -> None:
    login(client, "teacher.a", "teacher-a-password")
    response = client.post(
        "/classes",
        json={"name": "New Class", "subject": "Mathematics"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid CSRF token"


def test_teacher_can_create_and_list_only_owned_classes(client: TestClient) -> None:
    csrf_token = login(client, "teacher.a", "teacher-a-password")
    created = client.post(
        "/classes",
        headers={"X-CSRF-Token": csrf_token},
        json={"name": "New Class", "subject": "Mathematics"},
    )
    assert created.status_code == 201

    response = client.get("/classes")
    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"Class A", "New Class"}


def test_cross_tenant_roster_access_is_hidden(client: TestClient) -> None:
    login(client, "teacher.b", "teacher-b-password")
    own_classes = client.get("/classes").json()
    assert len(own_classes) == 1

    client.cookies.clear()
    login(client, "teacher.a", "teacher-a-password")
    response = client.get(f"/classes/{own_classes[0]['id']}/students")
    assert response.status_code == 404


def test_student_cannot_use_teacher_routes(client: TestClient) -> None:
    csrf_token = login(client, "student.a", "student-a-password")
    response = client.post(
        "/classes",
        headers={"X-CSRF-Token": csrf_token},
        json={"name": "Forbidden", "subject": "Mathematics"},
    )
    assert response.status_code == 403

    own_class = client.get("/student/class")
    assert own_class.status_code == 200
    assert own_class.json()["name"] == "Class A"
