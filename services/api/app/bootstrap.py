"""Prepare a synthetic deployment database without embedding demo credentials."""

import os
import secrets

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Tenant
from app.seed import seed_demo


def bootstrap() -> None:
    alembic = Config("alembic.ini")
    command.upgrade(alembic, "head")

    with SessionLocal() as db:
        already_seeded = db.scalar(
            select(Tenant.id).where(Tenant.name == "Synthetic Demo School")
        )
    if already_seeded:
        print("Synthetic demo database is already initialized.")
        return

    os.environ.setdefault("DEMO_TEACHER_PASSWORD", secrets.token_urlsafe(24))
    os.environ.setdefault("DEMO_STUDENT_PASSWORD", secrets.token_urlsafe(24))
    seed_demo()
    print("Synthetic demo database initialized.")


if __name__ == "__main__":
    bootstrap()
