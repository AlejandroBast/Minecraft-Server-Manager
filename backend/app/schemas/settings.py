"""Esquemas de las preferencias de la aplicación."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SettingsRead(BaseModel):
    values: dict[str, str | None]


class SettingsUpdate(BaseModel):
    """Actualización parcial: sólo las claves enviadas se modifican."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, str] = Field(min_length=1)
