"""Endpoints de plugins y mods, incluida la subida de archivos.

El jar se adjunta como multipart desde la interfaz: el usuario nunca copia
archivos a mano en las carpetas del servidor.
"""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, status

from app.api.deps import DbSession
from app.core.exceptions import ValidationError
from app.schemas.addon import AddonRead, AddonToggle
from app.services.addon_service import AddonKind, AddonService

router = APIRouter(prefix="/servers/{server_id}/addons", tags=["addons"])


@router.get("/{kind}", response_model=list[AddonRead])
def list_addons(server_id: int, kind: AddonKind, db: DbSession) -> list[AddonRead]:
    addons = AddonService(db).list_addons(server_id, kind)
    return [AddonRead.model_validate(addon) for addon in addons]


@router.post("/{kind}", response_model=AddonRead, status_code=status.HTTP_201_CREATED)
def upload_addon(
    server_id: int, kind: AddonKind, file: UploadFile, db: DbSession
) -> AddonRead:
    if not file.filename:
        raise ValidationError("El archivo no tiene nombre.")
    addon = AddonService(db).upload(server_id, kind, file.filename, file.file)
    return AddonRead.model_validate(addon)


@router.patch("/{kind}/{filename}", response_model=AddonRead)
def toggle_addon(
    server_id: int, kind: AddonKind, filename: str, payload: AddonToggle, db: DbSession
) -> AddonRead:
    addon = AddonService(db).set_enabled(server_id, kind, filename, payload.enabled)
    return AddonRead.model_validate(addon)


@router.delete("/{kind}/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_addon(server_id: int, kind: AddonKind, filename: str, db: DbSession) -> None:
    AddonService(db).delete(server_id, kind, filename)
