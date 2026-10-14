import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from alembic import command
from alembic.config import Config

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.models.base import Base

# Ensure tests strictly target workplace_test
TEST_DB_URL = settings.test_database_url


@pytest.fixture(scope="session")
def test_engine():
    """
    Session-scoped engine targeting the dedicated test database 'workplace_test'.
    Verifies that migrations run against an empty database.
    """
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    
    # 1. Clean out existing tables in workplace_test to start with a truly empty database
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS areas CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS sites CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        conn.commit()

    # 2. Run alembic migration programmatically against workplace_test
    alembic_cfg = Config("alembic.ini")
    os.environ["DATABASE_URL"] = TEST_DB_URL
    command.upgrade(alembic_cfg, "head")

    yield engine

    # Cleanup at end of session
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS areas CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS sites CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        conn.commit()
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_engine) -> Generator[Session, None, None]:
    """Provides an isolated database session per test with rollback cleanup."""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Test client for API testing."""
    with TestClient(app) as c:
        yield c
