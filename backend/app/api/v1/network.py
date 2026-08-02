"""Endpoints de red: diagnóstico, UPnP e instrucciones DNS."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.network import (
    DnsInstructionsRead,
    DnsRecordRead,
    DomainRequest,
    NetworkDiagnosisRead,
    PortActionResult,
)
from app.services import network_service
from app.services.server_service import ServerService

router = APIRouter(prefix="/network", tags=["network"])


@router.get("", response_model=NetworkDiagnosisRead)
def network_diagnosis(db: DbSession) -> NetworkDiagnosisRead:
    """Estado de la red y de los puertos de todos los servidores."""
    ports = sorted({server.port for server in ServerService(db).list_servers()})
    return NetworkDiagnosisRead.model_validate(network_service.diagnose(ports))


@router.post("/ports/{port}/open", response_model=PortActionResult)
def open_port(port: int) -> PortActionResult:
    success, message = network_service.open_port(port)
    return PortActionResult(success=success, message=message)


@router.post("/ports/{port}/close", response_model=PortActionResult)
def close_port(port: int) -> PortActionResult:
    success, message = network_service.close_port(port)
    return PortActionResult(success=success, message=message)


@router.post("/dns", response_model=DnsInstructionsRead)
def dns_instructions(payload: DomainRequest) -> DnsInstructionsRead:
    records = network_service.dns_instructions(
        payload.domain, network_service.get_public_ip(), payload.port
    )
    return DnsInstructionsRead(
        domain=payload.domain,
        records=[DnsRecordRead.model_validate(record) for record in records],
    )
