"""Esquemas de plugins y mods."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AddonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file: str
    size_bytes: int
    enabled: bool


class AddonToggle(BaseModel):
    enabled: bool
