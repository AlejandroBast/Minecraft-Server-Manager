"""Endpoints de la red privada de Tailscale."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AppSettings
from app.schemas.tailscale import LoginStarted, TailscaleStatusRead
from app.services import tailscale_service

router = APIRouter(prefix="/tailscale", tags=["tailscale"])


@router.get("", response_model=TailscaleStatusRead)
def tailscale_status() -> TailscaleStatusRead:
    return TailscaleStatusRead.model_validate(tailscale_service.status())


@router.post("/install", response_model=TailscaleStatusRead, status_code=status.HTTP_201_CREATED)
def install_tailscale(config: AppSettings) -> TailscaleStatusRead:
    """Descarga e instala Tailscale. Windows pedirá permisos de administrador."""
    tailscale_service.install(config)
    return TailscaleStatusRead.model_validate(tailscale_service.status())


@router.post("/login", response_model=LoginStarted)
def start_login() -> LoginStarted:
    """Inicia la sesión y devuelve el enlace que hay que abrir en el navegador."""
    url = tailscale_service.start_login()
    if url is None:
        estado = tailscale_service.status()
        if estado.running:
            return LoginStarted(login_url=None, message="La sesión ya estaba iniciada.")
        return LoginStarted(
            login_url=None,
            message="No se pudo obtener el enlace de acceso. Reinténtalo en unos segundos.",
        )
    return LoginStarted(login_url=url, message="Abre el enlace y entra con tu cuenta.")


@router.post("/disconnect", response_model=TailscaleStatusRead)
def disconnect() -> TailscaleStatusRead:
    tailscale_service.disconnect()
    return TailscaleStatusRead.model_validate(tailscale_service.status())
