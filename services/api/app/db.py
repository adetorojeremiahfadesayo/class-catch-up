from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


engine: Engine
SessionLocal: sessionmaker[Session]


def configure_database(database_url: str | None = None) -> Engine:
    global engine, SessionLocal

    url = database_url or get_settings().database_url
    connect_args = (
        {"check_same_thread": False, "timeout": 30}
        if url.startswith("sqlite")
        else {}
    )
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    if url.startswith("sqlite"):
        def configure_sqlite(connection, _) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")

        event.listen(engine, "connect", configure_sqlite)
    return engine


configure_database()


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
