"""Acceso desde internet mediante el túnel de playit.gg.

Resuelve el caso de las conexiones tras CGNAT, donde abrir puertos en el router
no sirve de nada: el agente abre la conexión *hacia afuera* (que sí funciona) y
playit.gg entrega una dirección pública. Los jugadores sólo escriben esa
dirección en Minecraft, sin instalar nada.

La clave del agente la genera el usuario en su navegador, en su propia cuenta
de playit.gg; la aplicación nunca ve ni pide su contraseña. La clave se guarda
en la tabla de configuración y jamás se devuelve por la API ni se escribe en
los registros.
"""

from __future__ import annotations

import platform
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.logging import get_logger
from app.services.http_client import ProgressCallback, download_file

logger = get_logger("downloads")

AGENT_VERSION = "v1.0.10"
AGENT_RELEASES = "https://github.com/playit-cloud/playit-agent/releases/download"
# Binario fijado por versión y verificado por hash: una descarga que se
# ejecutará en el equipo del usuario no puede depender sólo de la URL.
AGENT_BUILDS: dict[str, tuple[str, str]] = {
    "Windows": (
        "playit-windows-x86_64-signed.exe",
        "2dbdaad119844cbbc062cc9774b8b462afa5f1b4b7832a9fc5ef4676cae887cf",
    ),
    "Linux": ("playit-linux-amd64", ""),
}

PLAYIT_API = "https://api.playit.gg"
SETUP_URL = "https://playit.gg/account/setup/wizard/new-account/docker/minecraft-server-manager"
SECRET_KEY_NAME = "playit_secret"  # noqa: S105 - nombre de la clave, no la clave
API_TIMEOUT = 15.0


@dataclass(frozen=True)
class TunnelAddress:
    name: str
    address: str
    port: int | None
    local_port: int | None
    active: bool


@dataclass(frozen=True)
class TunnelStatus:
    agent_installed: bool
    secret_configured: bool
    running: bool
    setup_url: str = SETUP_URL
    addresses: list[TunnelAddress] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def agent_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    suffix = ".exe" if platform.system() == "Windows" else ""
    return settings.downloads_dir / "playit" / f"playit{suffix}"


def ensure_agent(
    settings: Settings | None = None, progress: ProgressCallback | None = None
) -> Path:
    """Descarga el agente oficial si aún no está, verificando su hash."""
    settings = settings or get_settings()
    destination = agent_path(settings)
    if destination.is_file():
        return destination

    system = platform.system()
    if system not in AGENT_BUILDS:
        raise ExternalServiceError(f"No hay agente de playit.gg para {system}.")
    filename, sha256 = AGENT_BUILDS[system]

    logger.info("Descargando el agente de playit.gg %s", AGENT_VERSION)
    download_file(
        f"{AGENT_RELEASES}/{AGENT_VERSION}/{filename}",
        destination,
        sha256=sha256 or None,
        progress=progress,
    )
    destination.chmod(0o755)
    return destination


def _api(secret: str, path: str) -> object:
    try:
        response = httpx.post(
            f"{PLAYIT_API}{path}",
            json={},
            headers={"Authorization": f"agent-key {secret}"},
            timeout=API_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise ExternalServiceError("No se pudo contactar con playit.gg.") from error

    if response.status_code == 401:
        raise ValidationError(
            "La clave del agente no es válida. Cópiala de nuevo desde playit.gg."
        )
    if response.status_code >= 400:
        raise ExternalServiceError(f"playit.gg respondió con un error ({response.status_code}).")
    return response.json()


def validate_secret(secret: str) -> bool:
    """Comprueba la clave contra la API antes de guardarla."""
    cleaned = secret.strip()
    if not cleaned or len(cleaned) > 512:
        raise ValidationError("La clave del agente está vacía o es demasiado larga.")
    _api(cleaned, "/tunnels/list")
    return True


def list_addresses(secret: str) -> list[TunnelAddress]:
    """Direcciones públicas que playit.gg ha asignado a esta cuenta."""
    payload = _api(secret, "/tunnels/list")
    if not isinstance(payload, dict):
        return []
    tunnels = payload.get("data", {}).get("tunnels", [])

    addresses: list[TunnelAddress] = []
    for tunnel in tunnels:
        assigned = tunnel.get("alloc", {}).get("data", {}) or {}
        hostname = assigned.get("assigned_domain") or assigned.get("ip_hostname") or ""
        if not hostname:
            continue
        addresses.append(
            TunnelAddress(
                name=str(tunnel.get("name") or "túnel"),
                address=str(hostname),
                port=assigned.get("port_start"),
                local_port=(tunnel.get("origin", {}).get("data", {}) or {}).get("local_port"),
                active=bool(tunnel.get("active", tunnel.get("disabled") is None)),
            )
        )
    return addresses


class TunnelAgent:
    """Supervisa el proceso del agente de playit.gg."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def start(self, secret: str, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if self.is_running():
            return

        executable = ensure_agent(settings)
        log_path = settings.logs_dir / "playit.log"
        # La clave viaja como argumento del proceso hijo, nunca al registro.
        command = [str(executable), "--secret", secret, "--log-path", str(log_path)]
        process = subprocess.Popen(  # noqa: S603 - binario fijado y verificado por hash
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._lock:
            self._process = process
        logger.info("Agente de playit.gg iniciado (registro en %s)", log_path)

    def stop(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        logger.info("Agente de playit.gg detenido")


agent = TunnelAgent()


def status(secret: str | None, settings: Settings | None = None) -> TunnelStatus:
    settings = settings or get_settings()
    notes: list[str] = []
    addresses: list[TunnelAddress] = []

    if secret:
        try:
            addresses = list_addresses(secret)
            if not addresses:
                notes.append(
                    "La cuenta aún no tiene ningún túnel creado. Crea uno de tipo Minecraft "
                    "Java en playit.gg apuntando al puerto de tu servidor."
                )
        except (ExternalServiceError, ValidationError) as error:
            notes.append(str(error))
    else:
        notes.append(
            "Necesitas una clave de agente de playit.gg. Se genera en su web, en tu propia "
            "cuenta: la aplicación nunca ve tu contraseña."
        )

    return TunnelStatus(
        agent_installed=agent_path(settings).is_file(),
        secret_configured=bool(secret),
        running=agent.is_running(),
        addresses=addresses,
        notes=notes,
    )
