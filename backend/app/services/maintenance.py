"""Tareas de mantenimiento al arrancar y bajo petición.

Dos problemas reales que resuelve:

1. Si la aplicación se cierra de golpe (corte de luz, cierre forzado), las
   filas quedan con estados «en marcha» que ya no son ciertos: los procesos
   Java murieron con ella. Al arrancar se corrigen.
2. Al eliminar un servidor, sus filas de backup caen en cascada pero los ZIP
   se quedan en disco. Aquí se recogen esos huérfanos.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.backup import Backup
from app.models.enums import BackupStatus, ServerStatus
from app.models.server import Server

logger = get_logger("app")


@dataclass(frozen=True)
class CleanupResult:
    orphan_backups_removed: int
    bytes_freed: int
    temp_files_removed: int


def recover_state() -> int:
    """Corrige los estados imposibles heredados de un cierre inesperado."""
    corrected = 0
    with session_scope() as session:
        servers = session.scalars(
            select(Server).where(Server.status != ServerStatus.STOPPED)
        ).all()
        for server in servers:
            if server.status is ServerStatus.INSTALLING:
                # La descarga se interrumpió: hay que recrearlo o reintentar.
                server.status = ServerStatus.ERROR
                server.last_error = (
                    "La instalación quedó a medias porque la aplicación se cerró. "
                    "Elimina el servidor y créalo de nuevo."
                )
            else:
                server.status = ServerStatus.STOPPED
            corrected += 1

        # Un backup no puede seguir «en curso» si el proceso que lo hacía murió.
        running_backups = session.scalars(
            select(Backup).where(Backup.status.in_([BackupStatus.RUNNING, BackupStatus.PENDING]))
        ).all()
        for backup in running_backups:
            backup.status = BackupStatus.FAILED
            backup.notes = "Interrumpida al cerrarse la aplicación."
            corrected += 1

    if corrected:
        logger.info("Estado recuperado: %d registros corregidos tras un cierre previo", corrected)
    return corrected


def cleanup(settings: Settings | None = None) -> CleanupResult:
    """Borra los ZIP sin fila en la base de datos y los temporales sueltos."""
    settings = settings or get_settings()

    with session_scope() as session:
        known = set(session.scalars(select(Backup.file)).all())

    removed = 0
    freed = 0
    if settings.backups_dir.is_dir():
        for archive in settings.backups_dir.glob("*.zip"):
            if archive.name not in known:
                freed += archive.stat().st_size
                archive.unlink(missing_ok=True)
                removed += 1
                logger.info("Backup huérfano eliminado: %s", archive.name)

    # Restos de descargas o restauraciones cortadas a mitad.
    temp_removed = 0
    for directory in (settings.backups_dir, settings.servers_dir, settings.temp_dir):
        if not directory.is_dir():
            continue
        for leftover in directory.glob("*.part"):
            leftover.unlink(missing_ok=True)
            temp_removed += 1

    return CleanupResult(
        orphan_backups_removed=removed, bytes_freed=freed, temp_files_removed=temp_removed
    )
