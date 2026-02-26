from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session


@dataclass(frozen=True)
class DbHandle:
    engine: Engine
    SessionLocal: sessionmaker


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False allows Streamlit + CLI to share the same sqlite file safely
    return create_engine(
        f"sqlite:///{db_path.as_posix()}",
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},
    )


def make_db(db_path: Path) -> DbHandle:
    engine = make_engine(db_path)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return DbHandle(engine=engine, SessionLocal=SessionLocal)


def get_session(db: DbHandle) -> Session:
    return db.SessionLocal()
