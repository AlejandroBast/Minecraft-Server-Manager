"""Detección del hardware y del entorno del equipo anfitrión.

Las llamadas caras (``java -version``, resolución de IP) se cachean unos
segundos porque el dashboard consulta este endpoint de forma periódica.
"""

from __future__ import annotations

import contextlib
import platform
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from app.core.logging import get_logger
from app.services.recommendations import HardwareSnapshot

logger = get_logger("app")

_JAVA_VERSION_RE = re.compile(r'version "(?P<version>[0-9._]+)"')
_CACHE_TTL_SECONDS = 30.0
_java_cache: tuple[float, JavaInfo] | None = None
_ip_cache: tuple[float, str] | None = None


@dataclass(frozen=True)
class CpuInfo:
    name: str
    physical_cores: int
    logical_cores: int
    frequency_mhz: float
    usage_percent: float


@dataclass(frozen=True)
class MemoryInfo:
    total_mb: int
    available_mb: int
    used_percent: float


@dataclass(frozen=True)
class DiskInfo:
    path: str
    total_gb: float
    free_gb: float
    used_percent: float


@dataclass(frozen=True)
class JavaInfo:
    installed: bool
    version: str | None = None
    major: int | None = None
    path: str | None = None
    managed: bool = False


@dataclass(frozen=True)
class NetworkInfo:
    hostname: str
    local_ip: str
    public_ip: str | None = None


@dataclass(frozen=True)
class SystemInfo:
    os: str
    os_version: str
    architecture: str
    python_version: str
    cpu: CpuInfo
    memory: MemoryInfo
    disk: DiskInfo
    java: JavaInfo
    network: NetworkInfo


def get_cpu_info() -> CpuInfo:
    frequency = psutil.cpu_freq()
    return CpuInfo(
        name=platform.processor() or platform.machine(),
        physical_cores=psutil.cpu_count(logical=False) or 1,
        logical_cores=psutil.cpu_count(logical=True) or 1,
        frequency_mhz=round(frequency.max or frequency.current, 0) if frequency else 0.0,
        usage_percent=psutil.cpu_percent(interval=None),
    )


def get_memory_info() -> MemoryInfo:
    memory = psutil.virtual_memory()
    return MemoryInfo(
        total_mb=memory.total // (1024**2),
        available_mb=memory.available // (1024**2),
        used_percent=memory.percent,
    )


def get_disk_info(path: Path) -> DiskInfo:
    """Espacio del volumen que contiene ``path`` (se sube hasta un padre existente)."""
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    usage = psutil.disk_usage(str(target))
    return DiskInfo(
        path=str(target),
        total_gb=round(usage.total / 1024**3, 2),
        free_gb=round(usage.free / 1024**3, 2),
        used_percent=usage.percent,
    )


def _parse_java_major(version: str) -> int | None:
    parts = version.split(".")
    try:
        first = int(parts[0])
    except ValueError:
        return None
    if first == 1 and len(parts) > 1:  # formato antiguo: 1.8.0_491 -> Java 8
        try:
            return int(parts[1])
        except ValueError:
            return None
    return first


def detect_java(java_dir: Path | None = None) -> JavaInfo:
    """Busca primero un runtime gestionado por la aplicación y luego el del sistema."""
    global _java_cache
    now = time.monotonic()
    if _java_cache and now - _java_cache[0] < _CACHE_TTL_SECONDS:
        return _java_cache[1]

    candidates: list[tuple[str, bool]] = []
    if java_dir and java_dir.exists():
        candidates.extend(
            (str(executable), True) for executable in sorted(java_dir.glob("*/bin/java.exe"))
        )
        candidates.extend(
            (str(executable), True) for executable in sorted(java_dir.glob("*/bin/java"))
        )
    system_java = shutil.which("java")
    if system_java:
        candidates.append((system_java, False))

    info = JavaInfo(installed=False)
    for executable, managed in candidates:
        try:
            completed = subprocess.run(  # noqa: S603 - ruta resuelta por el propio sistema
                [executable, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            logger.debug("No se pudo consultar %s: %s", executable, error)
            continue

        match = _JAVA_VERSION_RE.search(completed.stderr or completed.stdout)
        if not match:
            continue
        version = match.group("version")
        info = JavaInfo(
            installed=True,
            version=version,
            major=_parse_java_major(version),
            path=executable,
            managed=managed,
        )
        break

    _java_cache = (now, info)
    return info


def get_local_ip() -> str:
    """IP del equipo en la red local. No envía tráfico: sólo abre un socket UDP."""
    global _ip_cache
    now = time.monotonic()
    if _ip_cache and now - _ip_cache[0] < _CACHE_TTL_SECONDS:
        return _ip_cache[1]

    address = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(1.0)
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
    except OSError:
        with contextlib.suppress(OSError):
            address = socket.gethostbyname(socket.gethostname())

    _ip_cache = (now, address)
    return address


def get_network_info() -> NetworkInfo:
    # public_ip se resuelve en la fase 9 (red): requiere una consulta externa
    # y este endpoint lo llama el dashboard de forma periódica.
    return NetworkInfo(hostname=socket.gethostname(), local_ip=get_local_ip(), public_ip=None)


def get_system_info(servers_dir: Path, java_dir: Path) -> SystemInfo:
    return SystemInfo(
        os=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine(),
        python_version=platform.python_version(),
        cpu=get_cpu_info(),
        memory=get_memory_info(),
        disk=get_disk_info(servers_dir),
        java=detect_java(java_dir),
        network=get_network_info(),
    )


def to_hardware_snapshot(info: SystemInfo) -> HardwareSnapshot:
    """Adapta la información del sistema a la entrada del motor de recomendaciones."""
    return HardwareSnapshot(
        total_memory_mb=info.memory.total_mb,
        available_memory_mb=info.memory.available_mb,
        physical_cores=info.cpu.physical_cores,
        cpu_frequency_mhz=info.cpu.frequency_mhz,
        free_disk_gb=info.disk.free_gb,
    )
