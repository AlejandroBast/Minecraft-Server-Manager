"""Endpoints de información del equipo anfitrión y recomendaciones."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AppSettings
from app.models.enums import ServerType
from app.schemas.stats import CleanupResultRead
from app.schemas.system import RecommendationRead, SystemInfoRead
from app.services.maintenance import cleanup
from app.services.recommendations import recommend
from app.services.system_info import get_system_info, to_hardware_snapshot

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=SystemInfoRead)
def system_info(config: AppSettings) -> SystemInfoRead:
    info = get_system_info(config.servers_dir, config.java_dir)
    return SystemInfoRead.model_validate(info)


@router.post("/cleanup", response_model=CleanupResultRead)
def run_cleanup(config: AppSettings) -> CleanupResultRead:
    """Elimina copias huérfanas y ficheros temporales de descargas cortadas."""
    return CleanupResultRead.model_validate(cleanup(config))


@router.get("/recommendations", response_model=list[RecommendationRead])
def recommendations(config: AppSettings) -> list[RecommendationRead]:
    """Estimación de jugadores y memoria para cada tipo de servidor."""
    snapshot = to_hardware_snapshot(get_system_info(config.servers_dir, config.java_dir))
    return [
        RecommendationRead.model_validate(recommend(snapshot, server_type))
        for server_type in ServerType
    ]
