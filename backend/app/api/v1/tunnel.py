"""Endpoints del túnel de playit.gg (acceso desde internet tras CGNAT)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AppSettings, DbSession
from app.core.exceptions import ValidationError
from app.repositories.configuration_repository import ConfigurationRepository
from app.schemas.tunnel import TunnelSecretUpdate, TunnelStatusRead
from app.services import tunnel_service

router = APIRouter(prefix="/tunnel", tags=["tunnel"])


def _stored_secret(db: DbSession) -> str | None:
    row = ConfigurationRepository(db).get(tunnel_service.SECRET_KEY_NAME)
    return row.value if row and row.value else None


@router.get("", response_model=TunnelStatusRead)
def tunnel_status(db: DbSession, config: AppSettings) -> TunnelStatusRead:
    return TunnelStatusRead.model_validate(tunnel_service.status(_stored_secret(db), config))


@router.put("/secret", response_model=TunnelStatusRead)
def save_secret(
    payload: TunnelSecretUpdate, db: DbSession, config: AppSettings
) -> TunnelStatusRead:
    """Valida la clave contra playit.gg antes de guardarla."""
    secret = payload.secret.strip()
    tunnel_service.validate_secret(secret)

    ConfigurationRepository(db).set(tunnel_service.SECRET_KEY_NAME, secret)
    db.commit()
    return TunnelStatusRead.model_validate(tunnel_service.status(secret, config))


@router.delete("/secret", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(db: DbSession) -> None:
    tunnel_service.agent.stop()
    ConfigurationRepository(db).set(tunnel_service.SECRET_KEY_NAME, None)
    db.commit()


@router.post("/start", response_model=TunnelStatusRead)
def start_tunnel(db: DbSession, config: AppSettings) -> TunnelStatusRead:
    secret = _stored_secret(db)
    if not secret:
        raise ValidationError("Configura primero la clave del agente de playit.gg.")
    tunnel_service.agent.start(secret, config)
    return TunnelStatusRead.model_validate(tunnel_service.status(secret, config))


@router.post("/stop", response_model=TunnelStatusRead)
def stop_tunnel(db: DbSession, config: AppSettings) -> TunnelStatusRead:
    tunnel_service.agent.stop()
    return TunnelStatusRead.model_validate(tunnel_service.status(_stored_secret(db), config))
