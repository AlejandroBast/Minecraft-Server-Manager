"""Instalación completa de un servidor en segundo plano.

Se ejecuta después de responder al POST de creación: la estructura de carpetas
ya existe (fase 4) y aquí se descargan el runtime de Java y el server.jar. El
progreso se publica en el ``InstallTracker`` y el resultado (éxito o error) se
persiste en la fila del servidor.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.enums import ServerStatus
from app.models.server import Server
from app.services.http_client import download_file
from app.services.install_tracker import tracker
from app.services.java_manager import JavaManager
from app.services.version_catalog import (
    INSTALLER_TYPES,
    required_java_major,
    resolve_jar,
)

logger = get_logger("downloads")

SERVER_JAR_NAME = "server.jar"
INSTALLER_JAR_NAME = "installer.jar"
INSTALLER_TIMEOUT_SECONDS = 1800


def _run_installer(java_path: Path, root: Path) -> None:
    """Ejecuta el instalador de Forge/NeoForge, que despliega las librerías."""
    completed = subprocess.run(  # noqa: S603 - java gestionado + fichero verificado
        [str(java_path), "-jar", INSTALLER_JAR_NAME, "--installServer"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=INSTALLER_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stdout or "")[-1500:] + (completed.stderr or "")[-500:]
        raise ExternalServiceError(
            "El instalador del servidor terminó con errores.",
            details={"exit_code": completed.returncode, "output": tail},
        )
    # Limpieza: el instalador y su log no forman parte del servidor.
    (root / INSTALLER_JAR_NAME).unlink(missing_ok=True)
    (root / f"{INSTALLER_JAR_NAME}.log").unlink(missing_ok=True)


def _progress_callback(server_id: int, stage: str, detail: str):  # noqa: ANN202
    def callback(downloaded: int, total: int | None) -> None:
        fraction = downloaded / total if total else 0.0
        tracker.update(server_id, stage, fraction, detail)

    return callback


def run_full_install(server_id: int) -> None:
    """Descarga Java y el jar del servidor ``server_id`` y lo deja listo."""
    settings = get_settings()
    java_manager = JavaManager(settings.java_dir)

    with session_scope() as session:
        server = session.get(Server, server_id)
        if server is None:  # eliminado antes de empezar
            tracker.clear(server_id)
            return

        try:
            tracker.update(server_id, "java", 0.0, "Comprobando el Java necesario")
            major = required_java_major(server.version)
            java_path = java_manager.find_runtime(major)
            if java_path is None:
                tracker.update(server_id, "java", 0.0, f"Descargando Java {major} (Temurin)")
                java_path = java_manager.ensure_runtime(
                    major,
                    progress=_progress_callback(server_id, "java", f"Descargando Java {major}"),
                )

            tracker.update(server_id, "jar", 0.0, "Buscando la descarga del servidor")
            download = resolve_jar(server.type, server.version)
            root = settings.servers_dir / server.folder

            if server.type in INSTALLER_TYPES:
                installer_path = root / INSTALLER_JAR_NAME
                download_file(
                    download.url,
                    installer_path,
                    sha1=download.sha1,
                    progress=_progress_callback(
                        server_id, "jar", f"Descargando el instalador de {server.type.value}"
                    ),
                )
                tracker.update(
                    server_id,
                    "instalador",
                    0.0,
                    "Ejecutando el instalador (descarga librerías; puede tardar minutos)",
                )
                _run_installer(java_path, root)
                server.jar_file = None  # el arranque se resuelve por args de Forge
            else:
                download_file(
                    download.url,
                    root / SERVER_JAR_NAME,
                    sha256=download.sha256,
                    sha1=download.sha1,
                    md5=download.md5,
                    progress=_progress_callback(
                        server_id, "jar", f"Descargando {server.type.value} {server.version}"
                    ),
                )
                server.jar_file = SERVER_JAR_NAME

            server.java_path = str(java_path)
            server.build = download.build
            server.status = ServerStatus.STOPPED
            server.last_error = None
            tracker.update(server_id, "listo", 1.0, "Instalación completada")
            logger.info(
                "Instalación completa de %s (%s %s, Java %d)",
                server.name,
                server.type,
                server.version,
                major,
            )
        except Exception as error:
            server.status = ServerStatus.ERROR
            server.last_error = str(error)
            tracker.update(server_id, "error", 0.0, str(error))
            logger.exception("Instalación fallida del servidor %s", server_id)
