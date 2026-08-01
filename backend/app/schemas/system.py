"""Esquemas de la información del equipo y de las recomendaciones."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import ServerType


class _FromAttributes(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CpuInfoRead(_FromAttributes):
    name: str
    physical_cores: int
    logical_cores: int
    frequency_mhz: float
    usage_percent: float


class MemoryInfoRead(_FromAttributes):
    total_mb: int
    available_mb: int
    used_percent: float


class DiskInfoRead(_FromAttributes):
    path: str
    total_gb: float
    free_gb: float
    used_percent: float


class JavaInfoRead(_FromAttributes):
    installed: bool
    version: str | None
    major: int | None
    path: str | None
    managed: bool


class NetworkInfoRead(_FromAttributes):
    hostname: str
    local_ip: str
    public_ip: str | None


class SystemInfoRead(_FromAttributes):
    os: str
    os_version: str
    architecture: str
    python_version: str
    cpu: CpuInfoRead
    memory: MemoryInfoRead
    disk: DiskInfoRead
    java: JavaInfoRead
    network: NetworkInfoRead


class RecommendationRead(_FromAttributes):
    server_type: ServerType
    estimated_players: int
    memory_min_mb: int
    memory_max_mb: int
    warnings: list[str]
