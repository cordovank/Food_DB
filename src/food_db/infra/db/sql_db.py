from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session


@dataclass(frozen=True)
class DbHandle:
    engine: Engine
    SessionLocal: sessionmaker


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path.as_posix()}",
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},
    )


def make_db(db_path: Path) -> DbHandle:
    engine = make_engine(db_path)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return DbHandle(engine=engine, SessionLocal=SessionLocal)


@contextmanager
def get_session(db: DbHandle) -> Generator[Session, None, None]:
    """Yield a Session that rolls back automatically on any exception.

    Repository methods must still call s.commit() explicitly when
    they want to persist changes.  On exception the rollback fires
    before the caller sees the error, leaving the DB in a clean state.
    """
    session: Session = db.SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()