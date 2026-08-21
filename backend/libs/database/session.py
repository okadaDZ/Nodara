from __future__ import annotations

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from core.settings import settings
from libs.database.models import Base

# Normalize DATABASE_URL: if sqlite+aiosqlite was specified, sanitize to sqlite:/// for sync engine
raw_db_url = settings.database_url
if raw_db_url.startswith("sqlite+aiosqlite:///"):
    normalized_db_url = raw_db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
else:
    normalized_db_url = raw_db_url

if normalized_db_url.startswith("sqlite:///"):
    db_path = normalized_db_url.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    normalized_db_url,
    connect_args={"check_same_thread": False} if "sqlite" in normalized_db_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
