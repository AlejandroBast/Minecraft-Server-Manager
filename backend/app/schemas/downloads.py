"""Esquemas de catálogos de versiones y progreso de instalación."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import ServerType


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: str
    stable: bool


class VersionListRead(BaseModel):
    type: ServerType
    supported: bool
    reason: str | None
    versions: list[VersionRead]


class JavaRuntimeRead(BaseModel):
    major: int
    path: str


class InstallProgressRead(BaseModel):
    stage: str
    progress: float
    detail: str
