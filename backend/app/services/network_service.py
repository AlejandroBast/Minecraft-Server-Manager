"""Diagnóstico de red: IP pública, CGNAT, UPnP e instrucciones DNS.

La detección de CGNAT es la parte importante: se compara la IP que el router
cree tener con la que ve internet. Si no coinciden, el usuario está detrás del
NAT de su operador y **abrir puertos no servirá de nada**, por muy bien que
funcione el UPnP de su router. Decírselo de entrada le ahorra horas.
"""

from __future__ import annotations

import ipaddress
import threading
import time
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services import upnp
from app.services.http_client import get_text
from app.services.ports import is_port_free
from app.services.system_info import get_local_ip

logger = get_logger("app")

# Varias fuentes: si discrepan entre sí, el operador usa un pool de salida.
PUBLIC_IP_SOURCES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
)
PUBLIC_IP_TTL_SECONDS = 300.0
MAPPING_DESCRIPTION = "Minecraft Server Manager"

_ip_lock = threading.Lock()
_ip_cache: tuple[float, dict[str, str]] | None = None


@dataclass(frozen=True)
class PortStatus:
    port: int
    listening: bool
    upnp_mapped: bool


@dataclass(frozen=True)
class NetworkDiagnosis:
    local_ip: str
    public_ip: str | None
    router_external_ip: str | None
    upnp_available: bool
    behind_carrier_nat: bool
    ports: list[PortStatus] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def probe_public_ips(force: bool = False) -> dict[str, str]:
    """Consulta todas las fuentes y devuelve lo que ve cada una.

    Se preguntan varias a propósito: si discrepan, el operador saca el tráfico
    por un pool de direcciones (CGNAT), y eso hay que decírselo al usuario.
    """
    global _ip_cache
    now = time.monotonic()
    with _ip_lock:
        if not force and _ip_cache and now - _ip_cache[0] < PUBLIC_IP_TTL_SECONDS:
            return _ip_cache[1]

    observations: dict[str, str] = {}
    for source in PUBLIC_IP_SOURCES:
        try:
            candidate = get_text(source).strip()
            ipaddress.ip_address(candidate)
            observations[source] = candidate
        except Exception:
            logger.debug("Fuente de IP pública no disponible: %s", source)

    with _ip_lock:
        _ip_cache = (time.monotonic(), observations)
    return observations


def get_public_ip(force: bool = False) -> str | None:
    """IP pública vista desde internet, cacheada 5 minutos."""
    observations = probe_public_ips(force)
    return next(iter(observations.values()), None)


# Rangos que significan «tu router NO tiene una IP pública». Se enumeran a
# propósito en vez de usar ``is_private``, que también marca como privados los
# rangos de documentación y de pruebas, irrelevantes aquí.
_NON_ROUTABLE_RANGES = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",  # CGNAT: el NAT del operador
        "127.0.0.0/8",
        "169.254.0.0/16",
    )
)


def _is_private(address: str | None) -> bool:
    if not address:
        return False
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in _NON_ROUTABLE_RANGES)


def diagnose(ports: list[int]) -> NetworkDiagnosis:
    local_ip = get_local_ip()
    observations = probe_public_ips()
    public_ip = next(iter(observations.values()), None)
    gateway = upnp.discover_gateway()
    router_ip = upnp.get_external_ip(gateway) if gateway else None
    notes: list[str] = []

    behind_carrier_nat = False

    # Evidencia independiente del router: si dos servicios distintos te ven con
    # IPs distintas, tu tráfico sale por un pool de direcciones del operador.
    distinct_ips = sorted(set(observations.values()))
    if len(distinct_ips) > 1:
        behind_carrier_nat = True
        notes.append(
            "Internet te ve con varias IPs distintas ("
            + ", ".join(distinct_ips)
            + "): tu operador usa un pool de salida (CGNAT). Ninguna de esas IPs es tuya, así "
            "que abrir puertos no hará visible el servidor desde fuera. Para jugar con gente de "
            "fuera de tu casa necesitas un túnel (playit.gg, ngrok) o pedir una IP pública a tu "
            "operador."
        )

    if router_ip and public_ip:
        if _is_private(router_ip):
            behind_carrier_nat = True
            notes.append(
                "Tu router recibe una IP privada de tu operador (CGNAT): abrir el puerto no "
                "hará visible el servidor desde internet. Pide a tu operador una IP pública o "
                "usa un túnel (por ejemplo playit.gg)."
            )
        elif router_ip != public_ip:
            behind_carrier_nat = True
            notes.append(
                f"Tu router cree tener la IP {router_ip} pero internet te ve como {public_ip}: "
                "hay otro NAT por medio (habitual con fibra de operador). Abrir el puerto en el "
                "router puede no bastar."
            )

    if gateway is None:
        notes.append(
            "No se ha encontrado un router compatible con UPnP. Puedes abrir el puerto a mano "
            "desde la configuración de tu router (redirección de puertos)."
        )

    port_status: list[PortStatus] = []
    for port in ports:
        port_status.append(
            PortStatus(
                port=port,
                # is_port_free comprueba si se puede escuchar: si NO se puede,
                # es que algo (nuestro servidor) ya está escuchando ahí.
                listening=not is_port_free(port),
                upnp_mapped=upnp.has_port_mapping(gateway, port) if gateway else False,
            )
        )

    return NetworkDiagnosis(
        local_ip=local_ip,
        public_ip=public_ip,
        router_external_ip=router_ip,
        upnp_available=gateway is not None,
        behind_carrier_nat=behind_carrier_nat,
        ports=port_status,
        notes=notes,
    )


def open_port(port: int) -> tuple[bool, str]:
    """Intenta abrir el puerto por UPnP. Devuelve (éxito, mensaje)."""
    gateway = upnp.discover_gateway()
    if gateway is None:
        return False, (
            "No se ha encontrado un router con UPnP activo. Ábrelo a mano en la configuración "
            f"de tu router: redirección del puerto {port} (TCP) hacia {get_local_ip()}."
        )

    try:
        upnp.add_port_mapping(gateway, port, get_local_ip(), MAPPING_DESCRIPTION)
    except upnp.UpnpError as error:
        return False, f"El router rechazó abrir el puerto: {error}"
    return True, f"Puerto {port} abierto hacia {get_local_ip()}."


def close_port(port: int) -> tuple[bool, str]:
    gateway = upnp.discover_gateway()
    if gateway is None:
        return False, "No se ha encontrado un router con UPnP activo."
    try:
        upnp.delete_port_mapping(gateway, port)
    except upnp.UpnpError as error:
        return False, f"El router rechazó cerrar el puerto: {error}"
    return True, f"Puerto {port} cerrado."


@dataclass(frozen=True)
class DnsRecord:
    type: str
    name: str
    value: str
    explanation: str


def dns_instructions(domain: str, public_ip: str | None, port: int) -> list[DnsRecord]:
    """Registros que el usuario debe crear en su proveedor de dominio.

    No se administra ningún DNS: sólo se explica qué poner, como pide la
    especificación del proyecto.
    """
    host = domain.strip().lower().lstrip(".")
    records = [
        DnsRecord(
            type="A",
            name=host,
            value=public_ip or "(tu IP pública)",
            explanation="Apunta tu dominio a la IP de tu conexión.",
        )
    ]
    if port != 25565:
        records.append(
            DnsRecord(
                type="SRV",
                name=f"_minecraft._tcp.{host}",
                value=f"0 5 {port} {host}",
                explanation=(
                    f"Permite entrar escribiendo sólo «{host}», sin el «:{port}». "
                    "Formato: prioridad, peso, puerto y destino."
                ),
            )
        )
    return records
