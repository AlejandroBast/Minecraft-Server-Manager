"""Router raíz de la API v1.

Cada fase añade aquí su router; ningún módulo se registra directamente en la
aplicación para mantener un único punto de composición.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
