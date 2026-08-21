from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator, Generator

# Add backend root to sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Set test environment settings
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("USE_MOCK_AI_FALLBACK", "true")
os.environ.setdefault("LLM_API_KEY", "")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from libs.database.models import Base
from libs.database.session import get_db
from main import app

# In-memory SQLite engine for tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest_asyncio.fixture
async def client(db_session: Session) -> AsyncIterator[AsyncClient]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
