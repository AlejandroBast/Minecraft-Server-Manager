"""Esquemas del túnel de acceso desde internet.

La clave del agente entra por la API pero **nunca sale**: los esquemas de
lectura sólo indican si hay una configurada.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TunnelAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    address: str
    port: int | None
    local_port: int | None
    active: bool


class TunnelStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_installed: bool
    secret_configured: bool
    running: bool
    setup_url: str
    addresses: list[TunnelAddressRead]
    notes: list[str]


class TunnelSecretUpdate(BaseModel):
    secret: str = Field(min_length=8, max_length=512)
