"""Instalación en disco de un servidor recién creado.

Orquesta el sistema de ficheros y los generadores de configuración. Si algo
falla a mitad, revierte borrando la carpeta: nunca queda una instalación a
medias en ``servers/``.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.models.server import Server
from app.services.filesystem import ServerFilesystem
from app.services.properties_writer import (
    render_empty_json_list,
    render_eula,
    render_server_properties,
)

logger = get_logger("servers")


class ServerInstaller:
    def __init__(self, filesystem: ServerFilesystem) -> None:
        self._fs = filesystem

    def install(self, server: Server) -> Path:
        """Crea la carpeta del servidor con toda su configuración inicial.

        El jar y el runtime de Java llegan en la fase 5; esta instalación deja
        el directorio listo para recibirlos.
        """
        root = self._fs.create_layout(
            server.folder,
            plugins=server.type.supports_plugins,
            mods=server.type.supports_mods,
        )
        try:
            self._fs.write_file(server.folder, "eula.txt", render_eula())
            self._fs.write_file(
                server.folder, "server.properties", render_server_properties(server)
            )
            self._fs.write_file(server.folder, "ops.json", render_empty_json_list())
            self._fs.write_file(server.folder, "whitelist.json", render_empty_json_list())
        except Exception:
            # Revertir: mejor repetir la creación que dejar basura a medias.
            logger.exception("Instalación fallida de %s; se revierte la carpeta", server.folder)
            self._fs.remove(server.folder, missing_ok=True)
            raise

        logger.info("Servidor %s instalado en %s", server.name, root)
        return root

    def rewrite_configuration(self, server: Server) -> None:
        """Regenera ``server.properties`` tras un cambio de ajustes."""
        self._fs.write_file(server.folder, "server.properties", render_server_properties(server))
        logger.info("server.properties regenerado para %s", server.name)
