"""
SQLite engine and session factory.

The database file path is configurable for local dev and tests via ``DATABASE_URL``.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Default: repo-root/data/app.db (created on first run).
_DEFAULT_SQLITE = (
    Path(__file__).resolve().parent.parent / "data" / "app.db"
)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE}")

# SQLite needs check_same_thread=False when used with FastAPI async workers / multiple threads.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)
# autoflush=True so ORM writes are visible to subsequent queries in the same sync transaction.
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables registered on ``Base.metadata``."""
    # Import models so they register with Base.metadata before create_all.
    import db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
