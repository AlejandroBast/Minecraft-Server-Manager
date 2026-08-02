"""Endpoints de preferencias de la aplicación.

Sólo se admiten claves conocidas: aceptar claves arbitrarias convertiría esta
tabla en un almacén sin control y abriría la puerta a inyectar rutas.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.exceptions import ValidationError
from app.db.init_db import DEFAULT_CONFIGURATIONS
from app.repositories.configuration_repository import ConfigurationRepository
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_KEYS = frozenset(DEFAULT_CONFIGURATIONS)
PATH_KEYS = frozenset({"servers_dir", "backups_dir", "java_dir"})
MAX_VALUE_LENGTH = 500

# Secretos guardados en la misma tabla que las preferencias: se excluyen de la
# lectura y no pueden escribirse por aquí (tienen su propio endpoint validado).
SECRET_KEYS = frozenset({"playit_secret"})


def _visible(values: dict[str, str | None]) -> dict[str, str | None]:
    return {key: value for key, value in values.items() if key not in SECRET_KEYS}


@router.get("", response_model=SettingsRead)
def read_settings(db: DbSession) -> SettingsRead:
    return SettingsRead(values=_visible(ConfigurationRepository(db).all_as_dict()))


@router.put("", response_model=SettingsRead)
def update_settings(payload: SettingsUpdate, db: DbSession) -> SettingsRead:
    unknown = sorted(set(payload.values) - ALLOWED_KEYS)
    if unknown:
        raise ValidationError(
            "Hay claves de configuración desconocidas.", details={"keys": unknown}
        )

    for key, value in payload.values.items():
        if len(value) > MAX_VALUE_LENGTH:
            raise ValidationError(f"El valor de «{key}» es demasiado largo.")
        if key in PATH_KEYS and not Path(value).is_absolute():
            raise ValidationError(
                f"«{key}» debe ser una ruta absoluta.", details={"key": key, "value": value}
            )

    repository = ConfigurationRepository(db)
    for key, value in payload.values.items():
        repository.set(key, value)
    db.commit()
    return SettingsRead(values=_visible(repository.all_as_dict()))
