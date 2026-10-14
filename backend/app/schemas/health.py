from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatabaseStatus(BaseModel):
    status: str = Field(..., description="'connected' or 'unavailable'")
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class SchemaStatus(BaseModel):
    status: str = Field(..., description="'verified' or 'unverified'")
    alembic_version: Optional[str] = None
    tables_present: List[str] = []


class LiveResponse(BaseModel):
    status: str = Field(default="alive")
    service: str
    stage: str
    timestamp: datetime


class ReadyResponse(BaseModel):
    status: str = Field(..., description="'ready' or 'not_ready'")
    service: str
    stage: str
    timestamp: datetime
    database: DatabaseStatus
    schema_status: SchemaStatus
