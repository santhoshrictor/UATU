import time
from typing import Any, Dict, Generator, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings
from backend.app.core.logging import logger

# Primary Engine for Operational Database
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": int(settings.DB_CONNECT_TIMEOUT_SECONDS),
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_readiness(
    target_engine: Optional[Engine] = None,
    timeout_seconds: float = settings.DB_CONNECT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Checks database connection and schema state with a bounded timeout.
    Truthfully reports unavailability without exposing credentials or internal traces.
    """
    check_engine = target_engine or engine
    start_time = time.perf_counter()
    result: Dict[str, Any] = {
        "connected": False,
        "latency_ms": None,
        "server_version": None,
        "schema_ready": False,
        "alembic_version": None,
        "tables_present": [],
        "error": None,
    }

    try:
        with check_engine.connect() as conn:
            # 1. Test basic connectivity and retrieve real server version
            version_res = conn.execute(text("SELECT version();")).scalar()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            result["connected"] = True
            result["latency_ms"] = elapsed_ms
            result["server_version"] = version_res.split(" on ")[0] if version_res else "PostgreSQL (Unknown)"

            # 2. Check alembic_version table
            inspector = inspect(conn)
            table_names = inspector.get_table_names()
            result["tables_present"] = [t for t in ["alembic_version", "sites", "areas"] if t in table_names]

            if "alembic_version" in table_names:
                version_row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
                if version_row:
                    result["alembic_version"] = version_row[0]

            # Schema is ready if initial migration is applied and foundational tables exist
            if "sites" in table_names and "areas" in table_names and result["alembic_version"] is not None:
                result["schema_ready"] = True
            else:
                result["schema_ready"] = False

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        result["latency_ms"] = elapsed_ms
        result["connected"] = False
        result["schema_ready"] = False
        # Sanitize error: never return raw connection strings
        err_msg = str(exc)
        if "password" in err_msg.lower() or "@" in err_msg:
            result["error"] = "Database connection error (credentials masked)"
        else:
            result["error"] = err_msg.split("\n")[0][:200]
        logger.warning(f"Database readiness check failed: {result['error']}")

    return result
