"""Esquemas del diagnóstico de red."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PortStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    port: int
    listening: bool
    upnp_mapped: bool


class NetworkDiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    local_ip: str
    public_ip: str | None
    router_external_ip: str | None
    upnp_available: bool
    behind_carrier_nat: bool
    ports: list[PortStatusRead]
    notes: list[str]


class PortActionResult(BaseModel):
    success: bool
    message: str


class DnsRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    name: str
    value: str
    explanation: str


class DnsInstructionsRead(BaseModel):
    domain: str
    records: list[DnsRecordRead]


class DomainRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253, pattern=r"^[A-Za-z0-9.\-]+$")
    port: int = Field(default=25565, ge=1024, le=65535)
