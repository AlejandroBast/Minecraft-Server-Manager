"""Estadísticas en vivo de cada servidor.

Fuentes de cada dato:

* CPU y RAM   proceso Java y sus hijos, vía psutil
* Jugadores   Server List Ping (el mismo protocolo que usa el juego)
* TPS         comando ``tps`` de la familia Paper, cacheado 30 s para no
              llenar la consola del usuario de comandos automáticos
* Tamaño      recorrido de la carpeta del mundo, cacheado 60 s por ser caro
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

import psutil

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.enums import ServerStatus, ServerType
from app.models.server import Server
from app.services.minecraft_ping import ping
from app.services.process_manager import manager

logger = get_logger("servers")

TPS_CACHE_SECONDS = 30.0
SIZE_CACHE_SECONDS = 60.0
TPS_TYPES = frozenset({ServerType.PAPER, ServerType.PURPUR, ServerType.SPIGOT})
_TPS_PATTERN = re.compile(r"TPS from last .*?:\s*\*?([\d.]+)", re.IGNORECASE)

_cache_lock = threading.Lock()
_tps_cache: dict[int, tuple[float, float | None]] = {}
_size_cache: dict[int, tuple[float, int]] = {}

# psutil mide la CPU como diferencia respecto a la lectura anterior *del mismo
# objeto Process*. Si se creara uno nuevo en cada consulta, la primera lectura
# siempre sería 0.0 y nunca se vería el consumo real: por eso se reutilizan.
_processes: dict[int, psutil.Process] = {}


@dataclass(frozen=True)
class ServerStats:
    server_id: int
    running: bool
    cpu_percent: float | None
    memory_mb: float | None
    memory_percent_of_limit: float | None
    uptime_seconds: float | None
    online_players: int | None
    max_players: int | None
    tps: float | None
    world_size_bytes: int
    disk_free_gb: float


def _tracked_process(pid: int) -> psutil.Process:
    """Devuelve el ``Process`` reutilizado del pid, creándolo si hace falta."""
    with _cache_lock:
        process = _processes.get(pid)
        if process is None or not process.is_running():
            process = psutil.Process(pid)
            process.cpu_percent(interval=None)  # primera lectura de referencia
            _processes[pid] = process
        return process


def _process_usage(pid: int) -> tuple[float, float] | None:
    """CPU (%) y memoria (MB) del proceso Java, incluidos sus hijos."""
    try:
        process = _tracked_process(pid)
        with process.oneshot():
            # Mide desde la consulta anterior: como el dashboard pregunta cada
            # pocos segundos, la cifra representa el consumo reciente.
            cpu = process.cpu_percent(interval=None)
            memory = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                cpu += child.cpu_percent(interval=None)
                memory += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    return cpu / max(psutil.cpu_count() or 1, 1), memory / 1024**2


def _world_size(server: Server) -> int:
    now = time.monotonic()
    with _cache_lock:
        cached = _size_cache.get(server.id)
        if cached and now - cached[0] < SIZE_CACHE_SECONDS:
            return cached[1]

    root = get_settings().servers_dir / server.folder
    total = 0
    if root.is_dir():
        total = sum(item.stat().st_size for item in root.rglob("*") if item.is_file())

    with _cache_lock:
        _size_cache[server.id] = (time.monotonic(), total)
    return total


def _measure_tps(server: Server) -> float | None:
    """Pregunta el TPS a los servidores de la familia Paper."""
    if server.type not in TPS_TYPES or not manager.is_running(server.id):
        return None

    now = time.monotonic()
    with _cache_lock:
        cached = _tps_cache.get(server.id)
        if cached and now - cached[0] < TPS_CACHE_SECONDS:
            return cached[1]

    value: float | None = None
    try:
        # El índice se toma antes de enviar el comando: la respuesta puede
        # llegar en milisegundos y no debe perderse.
        index = manager.next_output_index(server.id)
        manager.send_command(server.id, "tps")
        if manager.wait_for_output(server.id, r"TPS from last", timeout=5, since=index):
            lines, _ = manager.output_since(server.id, index)
            for _, line in reversed(lines):
                match = _TPS_PATTERN.search(line)
                if match:
                    value = float(match.group(1))
                    break
    except AppError:  # el servidor pudo pararse entre medias
        value = None

    with _cache_lock:
        _tps_cache[server.id] = (time.monotonic(), value)
    return value


def collect(server: Server) -> ServerStats:
    settings = get_settings()
    running = manager.is_running(server.id)
    pid = manager.pid(server.id)
    usage = _process_usage(pid) if pid else None

    status = ping("127.0.0.1", server.port) if server.status is ServerStatus.ONLINE else None
    disk = psutil.disk_usage(str(settings.servers_dir))

    memory_mb = usage[1] if usage else None
    return ServerStats(
        server_id=server.id,
        running=running,
        cpu_percent=round(usage[0], 1) if usage else None,
        memory_mb=round(memory_mb, 1) if memory_mb else None,
        memory_percent_of_limit=(
            round(memory_mb / server.memory_max_mb * 100, 1)
            if memory_mb and server.memory_max_mb
            else None
        ),
        uptime_seconds=manager.uptime_seconds(server.id),
        online_players=status.online_players if status else None,
        max_players=status.max_players if status else None,
        tps=_measure_tps(server),
        world_size_bytes=_world_size(server),
        disk_free_gb=round(disk.free / 1024**3, 2),
    )


def forget(server_id: int) -> None:
    """Olvida las cachés de un servidor eliminado."""
    with _cache_lock:
        _tps_cache.pop(server_id, None)
        _size_cache.pop(server_id, None)
        for pid, process in list(_processes.items()):
            if not process.is_running():
                _processes.pop(pid, None)
