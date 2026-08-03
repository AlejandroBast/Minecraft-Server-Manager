"""Esquemas de la red privada de Tailscale."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PeerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    ip: str
    online: bool
    direct: bool
    relay: str | None
    os: str


class TailscaleStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    installed: bool
    running: bool
    needs_login: bool
    own_ip: str | None
    hostname: str | None
    login_url: str | None
    invite_url: str
    peers: list[PeerRead]
    notes: list[str]


class LoginStarted(BaseModel):
    login_url: str | None
    message: str
