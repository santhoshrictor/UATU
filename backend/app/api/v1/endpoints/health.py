from datetime import datetime, timezone
from fastapi import APIRouter, Response, status

from backend.app.core.config import settings
from backend.app.core.database import check_database_readiness
from backend.app.schemas.health import DatabaseStatus, LiveResponse, ReadyResponse, SchemaStatus

router = APIRouter()


@router.get("/live", response_model=LiveResponse, status_code=status.HTTP_200_OK)
def get_liveness() -> LiveResponse:
    """
    Liveness probe reporting whether the application process can respond.
    Does not require downstream services.
    """
    return LiveResponse(
        status="alive",
        service=settings.PROJECT_NAME,
        stage=settings.STAGE,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", response_model=ReadyResponse)
def get_readiness(response: Response) -> ReadyResponse:
    """
    Readiness probe testing the real database connection with a bounded timeout
    and verifying expected schema state.
    Returns HTTP 200 if connected and schema is verified; HTTP 503 if unavailable or degraded.
    """
    db_check = check_database_readiness()
    
    is_ready = db_check["connected"] and db_check["schema_ready"]
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        response.status_code = status.HTTP_200_OK

    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        service=settings.PROJECT_NAME,
        stage=settings.STAGE,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseStatus(
            status="connected" if db_check["connected"] else "unavailable",
            server_version=db_check.get("server_version"),
            latency_ms=db_check.get("latency_ms"),
            error=db_check.get("error"),
        ),
        schema_status=SchemaStatus(
            status="verified" if db_check["schema_ready"] else "unverified",
            alembic_version=db_check.get("alembic_version"),
            tables_present=db_check.get("tables_present", []),
        ),
    )
