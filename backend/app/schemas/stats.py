"""Esquemas de estadísticas y mantenimiento."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ServerStatsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: int
    running: bool
    cpu_percent: float | None
    memory_mb: float | None
    memory_percent_of_limit: float | None
    uptime_seconds: float | None
    online_players: int | None
    max_players: int | None
    tps: float | None
    world_size_bytes: int
    disk_free_gb: float


class CleanupResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orphan_backups_removed: int
    bytes_freed: int
    temp_files_removed: int
