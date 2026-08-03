"""Red privada con Tailscale: alternativa de baja latencia al túnel.

El túnel de playit.gg funciona en cualquier caso pero obliga a que el tráfico
dé un rodeo por sus servidores. Tailscale intenta conectar **directamente** a
cada jugador contigo: si lo consigue, dos personas de la misma ciudad pasan de
~180 ms a ~30 ms. Si no lo consigue, cae a un relé y queda parecido al túnel;
por eso la interfaz muestra, jugador a jugador, si la conexión es directa o por
relé — que es el dato que decide si merece la pena.

Todo se maneja desde la interfaz: instalación silenciosa, inicio de sesión con
un botón e invitaciones abriendo la página correcta. La única ventana que el
usuario verá es la de permisos de Windows, inevitable porque Tailscale instala
un adaptador de red.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.logging import get_logger
from app.services.http_client import ProgressCallback, download_file, get_json

logger = get_logger("downloads")

PKGS_INDEX = "https://pkgs.tailscale.com/stable/?mode=json"
PKGS_BASE = "https://pkgs.tailscale.com/stable"
ADMIN_INVITE_URL = "https://login.tailscale.com/admin/users"
CLI_TIMEOUT = 20.0
LOGIN_URL_TIMEOUT = 25.0

WINDOWS_CLI_PATHS = (
    Path(r"C:\Program Files\Tailscale\tailscale.exe"),
    Path(r"C:\Program Files (x86)\Tailscale\tailscale.exe"),
)


@dataclass(frozen=True)
class Peer:
    name: str
    ip: str
    online: bool
    direct: bool
    relay: str | None
    os: str


@dataclass(frozen=True)
class TailscaleStatus:
    installed: bool
    running: bool
    needs_login: bool
    own_ip: str | None
    hostname: str | None
    login_url: str | None
    invite_url: str = ADMIN_INVITE_URL
    peers: list[Peer] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def find_cli() -> Path | None:
    """Ruta del ejecutable de Tailscale si está instalado."""
    if platform.system() == "Windows":
        for candidate in WINDOWS_CLI_PATHS:
            if candidate.is_file():
                return candidate
    found = shutil.which("tailscale")
    return Path(found) if found else None


def _powershell() -> str:
    """Ruta absoluta de PowerShell.

    Se resuelve a propósito en vez de invocar «powershell.exe» a secas: el
    nombre suelto se buscaría en el PATH, que cualquier programa puede alterar.
    """
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("powershell")
    if found is None:
        raise ExternalServiceError("No se encuentra PowerShell en este equipo.")
    return found


def _run(cli: Path, *args: str, timeout: float = CLI_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - ejecutable propio y argumentos fijos
        [str(cli), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# -- instalación ---------------------------------------------------------


def latest_installer() -> tuple[str, str]:
    """Nombre y URL del instalador oficial para esta arquitectura."""
    index = get_json(PKGS_INDEX)
    if not isinstance(index, dict):
        raise ExternalServiceError("No se pudo consultar la lista de versiones de Tailscale.")

    machine = platform.machine().lower()
    architecture = "arm64" if "arm" in machine else "amd64" if machine.endswith("64") else "x86"
    filename = index.get("MSIs", {}).get(architecture)
    if not filename:
        raise ExternalServiceError(
            f"Tailscale no publica instalador para esta arquitectura ({architecture})."
        )
    return filename, f"{PKGS_BASE}/{filename}"


def _verify_signature(installer: Path) -> None:
    """Comprueba que el MSI está firmado por Tailscale.

    Se valida la firma digital en vez de fijar un hash porque el instalador se
    actualiza a menudo: la firma sigue siendo válida en cada versión nueva y
    protege igual contra un fichero manipulado.
    """
    if platform.system() != "Windows":
        return

    result = subprocess.run(  # noqa: S603 - comando fijo
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$s = Get-AuthenticodeSignature -LiteralPath '{installer}'; "
            "Write-Output $s.Status; Write-Output $s.SignerCertificate.Subject",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    output = (result.stdout or "").strip()
    if not output.startswith("Valid") or "Tailscale" not in output:
        installer.unlink(missing_ok=True)
        raise ExternalServiceError(
            "El instalador descargado no tiene una firma válida de Tailscale y se ha descartado.",
            details={"resultado": output[:200]},
        )


def install(settings: Settings | None = None, progress: ProgressCallback | None = None) -> Path:
    """Descarga el instalador oficial y lo ejecuta en silencio.

    Windows pedirá permisos de administrador: Tailscale instala un servicio y
    un adaptador de red, y eso no se puede hacer sin ellos.
    """
    settings = settings or get_settings()
    if platform.system() != "Windows":
        raise ValidationError("La instalación automática sólo está disponible en Windows.")

    filename, url = latest_installer()
    installer = settings.downloads_dir / "tailscale" / filename
    if not installer.is_file():
        logger.info("Descargando el instalador de Tailscale: %s", filename)
        download_file(url, installer, progress=progress)
    _verify_signature(installer)

    # Start-Process -Verb RunAs provoca el aviso de permisos de Windows; sin él
    # msiexec falla por falta de privilegios.
    result = subprocess.run(  # noqa: S603 - comando fijo sobre un fichero verificado
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$p = Start-Process msiexec.exe -Verb RunAs -Wait -PassThru "
            f"-ArgumentList '/i','{installer}','/quiet','/norestart'; exit $p.ExitCode",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    # 0 = correcto, 3010 = instalado pero pide reinicio.
    if result.returncode not in (0, 3010):
        raise ExternalServiceError(
            "La instalación de Tailscale no se completó. Si rechazaste el aviso de permisos "
            "de Windows, vuelve a intentarlo y acéptalo.",
            details={"exit_code": result.returncode},
        )

    cli = find_cli()
    if cli is None:
        raise ExternalServiceError(
            "Tailscale se instaló pero no se encuentra su ejecutable; reinicia el equipo."
        )
    logger.info("Tailscale instalado en %s", cli)
    return cli


# -- sesión y estado -----------------------------------------------------


def start_login() -> str | None:
    """Lanza el inicio de sesión y devuelve la URL que hay que abrir."""
    cli = find_cli()
    if cli is None:
        raise ValidationError("Tailscale no está instalado todavía.")

    process = subprocess.Popen(  # noqa: S603 - ejecutable propio y argumentos fijos
        [str(cli), "up", "--accept-routes=false"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None  # noqa: S101 - garantizado por Popen

    # «tailscale up» imprime la URL y se queda esperando a que el usuario la
    # abra; no se espera a que termine, sólo a que diga la dirección.
    found: list[str] = []

    def read_url() -> None:
        for line in process.stdout:  # type: ignore[union-attr]
            if "https://login.tailscale.com" in line:
                found.append(line.strip().split()[-1])
                return

    reader = threading.Thread(target=read_url, daemon=True)
    reader.start()
    reader.join(timeout=LOGIN_URL_TIMEOUT)
    return found[0] if found else None


def status() -> TailscaleStatus:
    cli = find_cli()
    if cli is None:
        return TailscaleStatus(
            installed=False,
            running=False,
            needs_login=False,
            own_ip=None,
            hostname=None,
            login_url=None,
            notes=[
                "Tailscale no está instalado. Púlsalo aquí y la aplicación lo instala sola; "
                "Windows te pedirá permiso porque añade un adaptador de red."
            ],
        )

    try:
        result = _run(cli, "status", "--json")
        payload = json.loads(result.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as error:
        logger.debug("No se pudo leer el estado de Tailscale: %s", error)
        return TailscaleStatus(
            installed=True,
            running=False,
            needs_login=False,
            own_ip=None,
            hostname=None,
            login_url=None,
            notes=["Tailscale está instalado pero no responde. Prueba a reiniciar el equipo."],
        )

    backend_state = payload.get("BackendState", "")
    own = payload.get("Self") or {}
    own_ips = own.get("TailscaleIPs") or []
    notes: list[str] = []

    peers: list[Peer] = []
    for peer in (payload.get("Peer") or {}).values():
        peer_ips = peer.get("TailscaleIPs") or []
        # Con dirección actual hay conexión directa; si sólo hay relé, el
        # tráfico pasa por los servidores de Tailscale y el ping sube.
        direct = bool(peer.get("CurAddr"))
        peers.append(
            Peer(
                name=str(peer.get("HostName") or peer.get("DNSName") or "equipo"),
                ip=str(peer_ips[0]) if peer_ips else "",
                online=bool(peer.get("Online")),
                direct=direct,
                relay=str(peer.get("Relay")) if peer.get("Relay") else None,
                os=str(peer.get("OS") or ""),
            )
        )
    peers.sort(key=lambda item: (not item.online, item.name.lower()))

    if backend_state == "NeedsLogin":
        notes.append("Falta iniciar sesión con tu cuenta para activar la red.")
    elif backend_state == "Stopped":
        notes.append("Tailscale está instalado pero desconectado.")

    conectados = [peer for peer in peers if peer.online]
    if conectados and all(not peer.direct for peer in conectados):
        notes.append(
            "Todas las conexiones van por relé, así que la latencia será parecida a la del "
            "túnel. Suele pasar cuando ambos lados están tras CGNAT."
        )

    return TailscaleStatus(
        installed=True,
        running=backend_state == "Running",
        needs_login=backend_state == "NeedsLogin",
        own_ip=str(own_ips[0]) if own_ips else None,
        hostname=str(own.get("HostName")) if own.get("HostName") else None,
        login_url=payload.get("AuthURL") or None,
        peers=peers,
        notes=notes,
    )


def disconnect() -> None:
    cli = find_cli()
    if cli is None:
        raise ValidationError("Tailscale no está instalado.")
    _run(cli, "down")
    logger.info("Tailscale desconectado")
