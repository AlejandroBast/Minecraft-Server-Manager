"""Copias de seguridad de servidores: crear, restaurar y eliminar.

Reglas de integridad:

* Con el servidor en marcha, antes de comprimir se envía ``save-off`` (para
  que Minecraft no escriba el mundo a mitad de copia) y ``save-all``; al
  terminar —bien o mal— se restaura ``save-on``.
* La restauración exige el servidor detenido, valida cada entrada del ZIP
  contra el sandbox (anti zip-slip) y reemplaza la carpeta por intercambio:
  primero se extrae a un directorio temporal y sólo si todo fue bien se
  sustituye la carpeta original.
"""

from __future__ import annotations

import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, ServerStateError, ValidationError
from app.core.logging import get_logger
from app.core.paths import is_within, resolve_within
from app.db.session import session_scope
from app.models.backup import Backup
from app.models.enums import BackupStatus, ServerStatus
from app.repositories.backup_repository import BackupRepository
from app.services.process_manager import manager
from app.services.server_service import ServerService

logger = get_logger("servers")

# Ficheros de bloqueo de sesión: copiarlos no aporta y puede fallar en Windows.
EXCLUDED_FILES = {"session.lock"}


class BackupService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repository = BackupRepository(session)
        self._servers = ServerService(session, self._settings)

    # -- consultas ---------------------------------------------------------

    def list_backups(self, server_id: int) -> list[Backup]:
        self._servers.get_server(server_id)
        return list(self._repository.list_for_server(server_id))

    def get_backup(self, backup_id: int) -> Backup:
        backup = self._repository.get(backup_id)
        if backup is None:
            raise NotFoundError("La copia de seguridad no existe.", details={"id": backup_id})
        return backup

    # -- creación ----------------------------------------------------------

    def register_backup(self, server_id: int, notes: str | None = None) -> Backup:
        """Crea la fila en estado RUNNING; la compresión ocurre después."""
        server = self._servers.get_server(server_id)
        if server.status is ServerStatus.INSTALLING:
            raise ServerStateError("Espera a que termine la instalación del servidor.")

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = Backup(
            server_id=server.id,
            file=f"{server.folder}-{timestamp}.zip",
            status=BackupStatus.RUNNING,
            notes=notes,
        )
        self._repository.add(backup)
        self._session.commit()
        return backup


def run_backup(backup_id: int) -> None:
    """Comprime la carpeta del servidor. Pensada para segundo plano."""
    settings = get_settings()
    with session_scope() as session:
        backup = session.get(Backup, backup_id)
        if backup is None:
            return
        server = backup.server
        source = settings.servers_dir / server.folder
        destination = resolve_within(settings.backups_dir, backup.file)

        was_running = manager.is_running(server.id)
        try:
            if was_running:
                # Congelar la escritura del mundo mientras se copia.
                manager.send_command(server.id, "save-off")
                manager.send_command(server.id, "save-all")
                manager.wait_for_output(server.id, r"Saved the game|save-all", timeout=15)

            size = _zip_directory(source, destination)
            backup.size_bytes = size
            backup.status = BackupStatus.COMPLETED
            logger.info("Backup %s completado (%d bytes)", backup.file, size)
        except Exception as error:
            backup.status = BackupStatus.FAILED
            backup.notes = str(error)
            destination.unlink(missing_ok=True)
            logger.exception("Backup %s fallido", backup.file)
        finally:
            if was_running:
                try:
                    manager.send_command(server.id, "save-on")
                except AppError:  # el servidor pudo pararse a mitad de copia
                    logger.warning("No se pudo reactivar save-on en el servidor %d", server.id)


def _zip_directory(source: Path, destination: Path) -> int:
    if not source.is_dir():
        raise ValidationError("La carpeta del servidor no existe en disco.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".part")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for item in sorted(source.rglob("*")):
            if item.name in EXCLUDED_FILES:
                continue
            relative = item.relative_to(source)
            try:
                if item.is_file():
                    bundle.write(item, relative.as_posix())
                elif item.is_dir():
                    bundle.mkdir(relative.as_posix())
            except OSError as error:
                # Un fichero bloqueado no debe tirar el backup completo.
                logger.warning("Se omite %s en el backup: %s", item, error)
    partial.replace(destination)
    return destination.stat().st_size


class BackupRestorer:
    """Restauración con intercambio de carpetas y protección anti zip-slip."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def restore(self, session: Session, backup_id: int) -> None:
        service = BackupService(session, self._settings)
        backup = service.get_backup(backup_id)
        if backup.status is not BackupStatus.COMPLETED:
            raise ValidationError("Sólo se puede restaurar una copia completada.")

        server = backup.server
        if server.status.is_active or manager.is_running(server.id):
            raise ServerStateError("Detén el servidor antes de restaurar una copia.")

        archive = resolve_within(self._settings.backups_dir, backup.file)
        if not archive.is_file():
            raise NotFoundError(
                "El fichero de la copia ya no existe en disco.", details={"file": backup.file}
            )

        target = resolve_within(self._settings.servers_dir, server.folder)
        staging = target.with_name(target.name + ".restore")
        retired = target.with_name(target.name + ".old")
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(retired, ignore_errors=True)

        try:
            self._extract_safely(archive, staging)
            if target.exists():
                target.replace(retired)
            staging.replace(target)
            shutil.rmtree(retired, ignore_errors=True)
        except Exception:
            # Nada a medias: se limpia el temporal y se recupera la original.
            shutil.rmtree(staging, ignore_errors=True)
            if retired.exists() and not target.exists():
                retired.replace(target)
            raise

        logger.info("Backup %s restaurado en %s", backup.file, server.folder)

    @staticmethod
    def _extract_safely(archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                # Anti zip-slip: toda entrada debe quedar dentro del destino.
                resolved = (destination / member.filename).resolve()
                if not is_within(destination, resolved):
                    raise ValidationError(
                        "La copia contiene rutas fuera de su carpeta y se rechaza.",
                        details={"entry": member.filename},
                    )
            bundle.extractall(destination)


def delete_backup(session: Session, backup_id: int, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    repository = BackupRepository(session)
    backup = repository.get(backup_id)
    if backup is None:
        raise NotFoundError("La copia de seguridad no existe.", details={"id": backup_id})

    archive = resolve_within(settings.backups_dir, backup.file)
    archive.unlink(missing_ok=True)
    repository.delete(backup)
    session.commit()
    logger.info("Backup %s eliminado", backup.file)
