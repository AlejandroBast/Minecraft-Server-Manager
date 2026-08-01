"""Esquemas de las copias de seguridad."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BackupStatus


class BackupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    file: str
    size_bytes: int
    status: BackupStatus
    notes: str | None
    created_at: datetime


class BackupCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=200)
