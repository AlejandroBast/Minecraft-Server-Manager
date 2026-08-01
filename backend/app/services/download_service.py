"""Instalación completa de un servidor en segundo plano.

Se ejecuta después de responder al POST de creación: la estructura de carpetas
ya existe (fase 4) y aquí se descargan el runtime de Java y el server.jar. El
progreso se publica en el ``InstallTracker`` y el resultado (éxito o error) se
persiste en la fila del servidor.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.enums import ServerStatus
from app.models.server import Server
from app.services.http_client import download_file
from app.services.install_tracker import tracker
from app.services.java_manager import JavaManager
from app.services.version_catalog import required_java_major, resolve_jar

logger = get_logger("downloads")

SERVER_JAR_NAME = "server.jar"


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
            jar_path = settings.servers_dir / server.folder / SERVER_JAR_NAME
            download_file(
                download.url,
                jar_path,
                sha256=download.sha256,
                sha1=download.sha1,
                md5=download.md5,
                progress=_progress_callback(
                    server_id, "jar", f"Descargando {server.type.value} {server.version}"
                ),
            )

            server.java_path = str(java_path)
            server.jar_file = SERVER_JAR_NAME
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
