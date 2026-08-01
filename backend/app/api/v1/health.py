"""Endpoint de diagnóstico: confirma API, base de datos y rutas de trabajo."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

_STARTED_AT = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    uptime_seconds: float


@router.get("/health", response_model=HealthResponse)
def health(db: DbSession, config: AppSettings) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:  # pragma: no cover - sólo si el fichero SQLite es ilegible
        database_status = "error"

    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        app=config.app_name,
        version=config.app_version,
        database=database_status,
        uptime_seconds=round(time.monotonic() - _STARTED_AT, 2),
    )
