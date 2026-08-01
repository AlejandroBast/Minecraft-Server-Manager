"""Registro en memoria del progreso de instalación de cada servidor.

Las instalaciones corren en hilos de fondo; el frontend consulta el avance por
HTTP. Es estado efímero: si la aplicación se reinicia a mitad, el servidor
queda en estado ``error`` y puede recrearse.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class InstallProgress:
    stage: str
    progress: float  # entre 0.0 y 1.0
    detail: str


class InstallTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[int, InstallProgress] = {}

    def update(self, server_id: int, stage: str, progress: float, detail: str = "") -> None:
        with self._lock:
            self._entries[server_id] = InstallProgress(
                stage=stage, progress=max(0.0, min(progress, 1.0)), detail=detail
            )

    def get(self, server_id: int) -> InstallProgress | None:
        with self._lock:
            return self._entries.get(server_id)

    def clear(self, server_id: int) -> None:
        with self._lock:
            self._entries.pop(server_id, None)


tracker = InstallTracker()
