"""Gestión de los procesos Java de los servidores.

Cada servidor en marcha es un ``subprocess.Popen`` independiente con un hilo
lector que consume su salida línea a línea: alimenta un buffer circular (para
la consola), detecta el «Done (…s)!» que marca el paso a EN LÍNEA y registra
el final del proceso para dejar el estado correcto en la base de datos.

La detención es siempre educada: se escribe ``stop`` por stdin y sólo si el
proceso no sale en el plazo se le mata. Matar a un servidor de Minecraft sin
dejarle guardar puede corromper el mundo.
"""

from __future__ import annotations

import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ServerStateError, ValidationError
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.enums import ServerStatus
from app.models.server import Server

logger = get_logger("servers")
console_logger = get_logger("console")

_DONE_PATTERN = re.compile(r"Done \([\d.,]+s\)!")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

BUFFER_LINES = 1000
STOP_TIMEOUT_SECONDS = 30.0
MAX_COMMAND_LENGTH = 500


@dataclass
class ManagedProcess:
    process: subprocess.Popen
    started_at: float
    buffer: deque[tuple[int, str]] = field(default_factory=lambda: deque(maxlen=BUFFER_LINES))
    next_index: int = 0
    expected_stop: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, line: str) -> None:
        with self.lock:
            self.buffer.append((self.next_index, line))
            self.next_index += 1

    def since(self, index: int) -> tuple[list[tuple[int, str]], int]:
        with self.lock:
            lines = [(i, line) for i, line in self.buffer if i >= index]
            return lines, self.next_index


def _set_status(server_id: int, status: ServerStatus, error: str | None = None) -> None:
    with session_scope() as session:
        server = session.get(Server, server_id)
        if server is not None:
            server.status = status
            if error is not None or status is ServerStatus.ONLINE:
                server.last_error = error


class ProcessManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[int, ManagedProcess] = {}

    # -- consultas ---------------------------------------------------------

    def is_running(self, server_id: int) -> bool:
        with self._lock:
            entry = self._entries.get(server_id)
        return entry is not None and entry.process.poll() is None

    def uptime_seconds(self, server_id: int) -> float | None:
        with self._lock:
            entry = self._entries.get(server_id)
        if entry is None or entry.process.poll() is not None:
            return None
        return time.monotonic() - entry.started_at

    def output_since(self, server_id: int, index: int) -> tuple[list[tuple[int, str]], int]:
        with self._lock:
            entry = self._entries.get(server_id)
        if entry is None:
            return [], 0
        return entry.since(index)

    # -- ciclo de vida -----------------------------------------------------

    def _build_command(self, server: Server, jar_path: Path) -> list[str]:
        return [
            server.java_path or "java",
            f"-Xms{server.memory_min_mb}M",
            f"-Xmx{server.memory_max_mb}M",
            "-jar",
            str(jar_path),
            "nogui",
        ]

    def start(self, server: Server) -> None:
        if server.status not in {ServerStatus.STOPPED, ServerStatus.ERROR}:
            raise ServerStateError(
                "El servidor sólo puede iniciarse si está detenido.",
                details={"status": server.status},
            )
        if self.is_running(server.id):
            raise ServerStateError("El servidor ya tiene un proceso en marcha.")

        settings = get_settings()
        root = settings.servers_dir / server.folder
        jar_path = root / (server.jar_file or "server.jar")
        if not jar_path.is_file():
            raise ValidationError(
                "El servidor no tiene server.jar; su instalación no terminó bien.",
                details={"jar": str(jar_path)},
            )
        if not server.java_path or not Path(server.java_path).is_file():
            raise ValidationError(
                "No se encuentra el Java de este servidor; recrea el servidor.",
                details={"java": server.java_path},
            )

        command = self._build_command(server, jar_path)
        logger.info("Iniciando %s: %s", server.name, " ".join(command))
        process = subprocess.Popen(  # noqa: S603 - comando construido internamente
            command,
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        entry = ManagedProcess(process=process, started_at=time.monotonic())
        with self._lock:
            self._entries[server.id] = entry

        _set_status(server.id, ServerStatus.STARTING)
        threading.Thread(
            target=self._reader,
            args=(server.id, server.name, entry),
            name=f"console-{server.id}",
            daemon=True,
        ).start()

    def _reader(self, server_id: int, server_name: str, entry: ManagedProcess) -> None:
        online = False
        assert entry.process.stdout is not None  # noqa: S101 - garantizado por Popen
        for raw_line in entry.process.stdout:
            line = raw_line.rstrip("\r\n")
            entry.append(line)
            console_logger.info("[%s] %s", server_name, line)
            if not online and _DONE_PATTERN.search(line):
                online = True
                _set_status(server_id, ServerStatus.ONLINE)
                logger.info("%s está EN LÍNEA", server_name)

        exit_code = entry.process.wait()
        if entry.expected_stop or exit_code == 0:
            _set_status(server_id, ServerStatus.STOPPED)
            logger.info("%s detenido (código %d)", server_name, exit_code)
        else:
            _set_status(
                server_id,
                ServerStatus.ERROR,
                error=f"El proceso terminó de forma inesperada (código {exit_code}).",
            )
            logger.error("%s terminó con código %d", server_name, exit_code)

    def send_command(self, server_id: int, command: str) -> str:
        """Envía un comando de consola al proceso. Devuelve el comando limpio."""
        cleaned = _CONTROL_CHARS.sub("", command).strip().lstrip("/")
        if not cleaned or "\n" in command or len(cleaned) > MAX_COMMAND_LENGTH:
            raise ValidationError("Comando de consola no válido.")

        with self._lock:
            entry = self._entries.get(server_id)
        if entry is None or entry.process.poll() is not None or entry.process.stdin is None:
            raise ServerStateError("El servidor no está en marcha.")

        entry.process.stdin.write(cleaned + "\n")
        entry.process.stdin.flush()
        console_logger.info("[#%d] > %s", server_id, cleaned)
        return cleaned

    def stop(self, server_id: int, *, timeout: float = STOP_TIMEOUT_SECONDS) -> None:
        with self._lock:
            entry = self._entries.get(server_id)
        if entry is None or entry.process.poll() is not None:
            # Sin proceso vivo: se corrige el estado y listo (p. ej. tras un
            # reinicio de la aplicación con la fila aún en "online").
            _set_status(server_id, ServerStatus.STOPPED)
            return

        entry.expected_stop = True
        _set_status(server_id, ServerStatus.STOPPING)
        try:
            if entry.process.stdin is not None:
                entry.process.stdin.write("stop\n")
                entry.process.stdin.flush()
        except OSError:
            pass

        try:
            entry.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Servidor %d no respondió a stop; se fuerza el cierre", server_id)
            entry.process.kill()
            entry.process.wait(timeout=10)

    def restart(self, server: Server) -> None:
        _set_status(server.id, ServerStatus.RESTARTING)
        self.stop(server.id)
        with session_scope() as session:
            fresh = session.get(Server, server.id)
            if fresh is None:
                raise NotFoundError("El servidor ya no existe.")
            self.start(fresh)

    def stop_all(self) -> None:
        """Detiene todos los procesos al apagar la aplicación."""
        with self._lock:
            server_ids = list(self._entries)
        for server_id in server_ids:
            try:
                self.stop(server_id, timeout=15)
            except Exception:  # pragma: no cover - apagado de emergencia
                logger.exception("No se pudo detener el servidor %d al salir", server_id)


manager = ProcessManager()
