import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app import db as db_module
from app.auth import password_hasher
from app.main import create_app
from app.models import Base, Enrollment, Role, SchoolClass, Tenant, User


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    engine = db_module.configure_database(database_url)
    Base.metadata.create_all(engine)

    with db_module.SessionLocal.begin() as db:
        tenant_a = Tenant(name="Tenant A")
        tenant_b = Tenant(name="Tenant B")
        db.add_all([tenant_a, tenant_b])
        db.flush()

        teacher_a = User(
            tenant_id=tenant_a.id,
            username="teacher.a",
            display_name="Teacher A",
            password_hash=password_hasher.hash("teacher-a-password"),
            role=Role.teacher,
        )
        teacher_b = User(
            tenant_id=tenant_b.id,
            username="teacher.b",
            display_name="Teacher B",
            password_hash=password_hasher.hash("teacher-b-password"),
            role=Role.teacher,
        )
        student_a = User(
            tenant_id=tenant_a.id,
            username="student.a",
            display_name="Student A",
            password_hash=password_hasher.hash("student-a-password"),
            role=Role.student,
        )
        db.add_all([teacher_a, teacher_b, student_a])
        db.flush()

        class_a = SchoolClass(
            tenant_id=tenant_a.id,
            owner_teacher_id=teacher_a.id,
            name="Class A",
            subject="Mathematics",
        )
        class_b = SchoolClass(
            tenant_id=tenant_b.id,
            owner_teacher_id=teacher_b.id,
            name="Class B",
            subject="Mathematics",
        )
        db.add_all([class_a, class_b])
        db.flush()
        db.add(
            Enrollment(
                tenant_id=tenant_a.id,
                class_id=class_a.id,
                user_id=student_a.id,
            )
        )

    with TestClient(create_app()) as test_client:
        yield test_client
