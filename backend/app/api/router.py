"""Router raíz de la API v1.

Cada fase añade aquí su router; ningún módulo se registra directamente en la
aplicación para mantener un único punto de composición.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    addons,
    backups,
    console,
    downloads,
    health,
    network,
    servers,
    settings,
    system,
    tailscale,
    tunnel,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(servers.router)
api_router.include_router(console.router)
api_router.include_router(backups.router)
api_router.include_router(addons.router)
api_router.include_router(network.router)
api_router.include_router(tunnel.router)
api_router.include_router(tailscale.router)
api_router.include_router(system.router)
api_router.include_router(settings.router)
api_router.include_router(downloads.router)
