"""Reglas de negocio de los servidores.

No importa FastAPI: recibe esquemas y una sesión, devuelve modelos o lanza
excepciones de dominio. Desde la fase 4 la creación también materializa el
servidor en disco (carpeta, EULA, configuración); el jar llega en la fase 5.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, ServerStateError
from app.core.logging import get_logger
from app.core.paths import sanitize_folder_name, to_folder_slug
from app.models.enums import ServerStatus
from app.models.server import Server
from app.repositories.server_repository import ServerRepository
from app.schemas.server import ServerCreate, ServerUpdate
from app.services.filesystem import ServerFilesystem
from app.services.ports import is_port_free
from app.services.server_installer import ServerInstaller

logger = get_logger("servers")

# Campos que exigen reiniciar el servidor: no se tocan mientras está activo.
RESTART_REQUIRED_FIELDS = frozenset({"port", "memory_min_mb", "memory_max_mb"})

# Campos que se reflejan en server.properties.
PROPERTIES_FIELDS = frozenset(
    {
        "port",
        "max_players",
        "motd",
        "difficulty",
        "gamemode",
        "online_mode",
        "hardcore",
        "allow_commands",
        "whitelist_enabled",
        "seed",
    }
)


class ServerService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._repository = ServerRepository(session)
        self._settings = settings or get_settings()
        self._filesystem = ServerFilesystem(self._settings.servers_dir)
        self._installer = ServerInstaller(self._filesystem)

    def list_servers(self) -> Sequence[Server]:
        return self._repository.list_all()

    def get_server(self, server_id: int) -> Server:
        server = self._repository.get(server_id)
        if server is None:
            raise NotFoundError(
                "El servidor solicitado no existe.", details={"server_id": server_id}
            )
        return server

    def create_server(self, data: ServerCreate) -> tuple[Server, list[str]]:
        name = sanitize_folder_name(data.name)
        if self._repository.get_by_name(name) is not None:
            raise ConflictError("Ya existe un servidor con ese nombre.", details={"name": name})

        conflicting = self._repository.get_by_port(data.port)
        if conflicting is not None:
            raise ConflictError(
                f"El puerto {data.port} ya lo usa el servidor «{conflicting.name}».",
                details={"port": data.port, "server_id": conflicting.id},
            )

        warnings: list[str] = []
        if not is_port_free(data.port):
            # Sólo se avisa: podría ser un proceso temporal y no corresponde
            # bloquear al usuario por ello.
            warnings.append(
                f"Otro programa del equipo está usando el puerto {data.port} en este momento."
            )

        server = Server(
            **data.model_dump(exclude={"name"}),
            name=name,
            folder=self._unique_folder(name),
            status=ServerStatus.STOPPED,
        )
        self._repository.add(server)

        # Disco antes de confirmar la transacción: si la instalación falla, la
        # fila se revierte; si el commit fallara, el instalador ya limpió todo
        # lo suyo y la carpeta puede recrearse sin conflicto al reintentar.
        try:
            self._installer.install(server)
            self._session.commit()
        except Exception:
            self._session.rollback()
            self._filesystem.remove(server.folder, missing_ok=True)
            raise

        logger.info("Servidor creado: %s (%s %s)", server.name, server.type, server.version)
        return server, warnings

    def update_server(self, server_id: int, data: ServerUpdate) -> Server:
        server = self.get_server(server_id)
        changes = data.model_dump(exclude_unset=True)

        if server.status.is_active:
            blocked = RESTART_REQUIRED_FIELDS & changes.keys()
            if blocked:
                raise ServerStateError(
                    "Detén el servidor antes de cambiar estos ajustes.",
                    details={"fields": sorted(blocked), "status": server.status},
                )

        if "name" in changes:
            new_name = sanitize_folder_name(changes["name"])
            existing = self._repository.get_by_name(new_name)
            if existing is not None and existing.id != server.id:
                raise ConflictError(
                    "Ya existe un servidor con ese nombre.", details={"name": new_name}
                )
            changes["name"] = new_name

        if "port" in changes:
            conflicting = self._repository.get_by_port(changes["port"], exclude_id=server.id)
            if conflicting is not None:
                raise ConflictError(
                    f"El puerto {changes['port']} ya lo usa el servidor «{conflicting.name}».",
                    details={"port": changes["port"]},
                )

        memory_min = changes.get("memory_min_mb", server.memory_min_mb)
        memory_max = changes.get("memory_max_mb", server.memory_max_mb)
        if memory_max < memory_min:
            raise ConflictError("La memoria máxima no puede ser menor que la mínima.")

        for field, value in changes.items():
            setattr(server, field, value)

        self._session.commit()

        # La base de datos es la fuente de verdad: el fichero se regenera para
        # que el próximo arranque del servidor use los ajustes nuevos.
        if PROPERTIES_FIELDS & changes.keys() and self._filesystem.exists(server.folder):
            self._installer.rewrite_configuration(server)

        logger.info("Servidor actualizado: %s (%s)", server.name, ", ".join(sorted(changes)))
        return server

    def delete_server(self, server_id: int) -> None:
        server = self.get_server(server_id)
        if server.status.is_active:
            raise ServerStateError(
                "Detén el servidor antes de eliminarlo.",
                details={"status": server.status},
            )
        # missing_ok: los servidores registrados antes de la fase 4 no tienen
        # carpeta en disco, y un borrado repetido no debe fallar.
        self._filesystem.remove(server.folder, missing_ok=True)
        self._repository.delete(server)
        self._session.commit()
        logger.info("Servidor eliminado: %s", server.name)

    def _unique_folder(self, name: str) -> str:
        base = to_folder_slug(name)
        candidate = base
        suffix = 2
        while (
            self._repository.get_by_folder(candidate) is not None
            or self._filesystem.exists(candidate)
        ):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate
