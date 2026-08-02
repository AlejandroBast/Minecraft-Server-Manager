"""Cliente UPnP mínimo para abrir el puerto en el router.

Se implementa a mano (descubrimiento SSDP + dos llamadas SOAP) en lugar de
depender de ``miniupnpc``: esa librería es una extensión en C sin ruedas
fiables para las versiones nuevas de Python, y el usuario final no debe pelear
con compiladores para instalar la aplicación.

Todo es de mejor esfuerzo: si el router no responde o tiene UPnP desactivado,
se informa y la interfaz muestra las instrucciones manuales.
"""

from __future__ import annotations

import socket
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.core.logging import get_logger

logger = get_logger("app")

SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_TIMEOUT = 3.0
SOAP_TIMEOUT = 8.0

# Los routers implementan una de estas dos: IP directa o PPPoE.
WAN_SERVICES = (
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
)
UPNP_NS = {"d": "urn:schemas-upnp-org:device-1-0"}

_MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDRESS[0]}:{SSDP_ADDRESS[1]}\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\n"
    "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n"
)


class UpnpError(Exception):
    """El router no responde, no tiene UPnP o rechaza la operación."""


@dataclass(frozen=True)
class Gateway:
    control_url: str
    service_type: str


def discover_gateway(timeout: float = SSDP_TIMEOUT) -> Gateway | None:
    """Busca el router por SSDP y devuelve su URL de control, o ``None``."""
    location = _discover_location(timeout)
    if location is None:
        return None
    try:
        response = httpx.get(location, timeout=SOAP_TIMEOUT)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)  # noqa: S314 - respuesta del router local
    except (httpx.HTTPError, ElementTree.ParseError) as error:
        logger.debug("No se pudo leer la descripción UPnP: %s", error)
        return None

    for service in root.iter(f"{{{UPNP_NS['d']}}}service"):
        service_type = service.findtext(f"{{{UPNP_NS['d']}}}serviceType", "")
        control_path = service.findtext(f"{{{UPNP_NS['d']}}}controlURL", "")
        if service_type in WAN_SERVICES and control_path:
            return Gateway(control_url=urljoin(location, control_path), service_type=service_type)
    return None


def _discover_location(timeout: float) -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.settimeout(timeout)
        try:
            probe.sendto(_MSEARCH.encode(), SSDP_ADDRESS)
            data, _ = probe.recvfrom(65507)
        except OSError:
            return None

    for line in data.decode(errors="replace").splitlines():
        if line.lower().startswith("location:"):
            return line.split(":", 1)[1].strip()
    return None


def _soap(gateway: Gateway, action: str, arguments: dict[str, str | int]) -> dict[str, str]:
    body_args = "".join(f"<{key}>{value}</{key}>" for key, value in arguments.items())
    envelope = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<s:Body><u:{action} xmlns:u="{gateway.service_type}">{body_args}'
        f"</u:{action}></s:Body></s:Envelope>"
    )
    try:
        response = httpx.post(
            gateway.control_url,
            content=envelope.encode(),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"{gateway.service_type}#{action}"',
            },
            timeout=SOAP_TIMEOUT,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)  # noqa: S314 - respuesta del router local
    except (httpx.HTTPError, ElementTree.ParseError) as error:
        raise UpnpError(f"El router rechazó la operación {action}.") from error

    return {
        element.tag.rpartition("}")[2]: (element.text or "")
        for element in root.iter()
        if element.text and not element.tag.endswith(("Envelope", "Body"))
    }


def get_external_ip(gateway: Gateway) -> str | None:
    """IP que el router cree tener en su lado WAN."""
    try:
        return _soap(gateway, "GetExternalIPAddress", {}).get("NewExternalIPAddress")
    except UpnpError:
        return None


def add_port_mapping(
    gateway: Gateway, port: int, internal_ip: str, description: str, protocol: str = "TCP"
) -> None:
    _soap(
        gateway,
        "AddPortMapping",
        {
            "NewRemoteHost": "",
            "NewExternalPort": port,
            "NewProtocol": protocol,
            "NewInternalPort": port,
            "NewInternalClient": internal_ip,
            "NewEnabled": 1,
            "NewPortMappingDescription": description,
            "NewLeaseDuration": 0,  # permanente: sobrevive a reinicios del programa
        },
    )
    logger.info("UPnP: puerto %d abierto hacia %s", port, internal_ip)


def delete_port_mapping(gateway: Gateway, port: int, protocol: str = "TCP") -> None:
    _soap(
        gateway,
        "DeletePortMapping",
        {"NewRemoteHost": "", "NewExternalPort": port, "NewProtocol": protocol},
    )
    logger.info("UPnP: puerto %d cerrado", port)


def has_port_mapping(gateway: Gateway, port: int, protocol: str = "TCP") -> bool:
    try:
        result = _soap(
            gateway,
            "GetSpecificPortMappingEntry",
            {"NewRemoteHost": "", "NewExternalPort": port, "NewProtocol": protocol},
        )
    except UpnpError:
        return False
    return bool(result.get("NewInternalClient"))
