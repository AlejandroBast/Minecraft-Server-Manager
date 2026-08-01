"""Reglas de negocio de los servidores.

No importa FastAPI: recibe esquemas y una sesión, devuelve modelos o lanza
excepciones de dominio. En esta fase sólo gestiona el registro en base de
datos; la creación de la carpeta y la descarga del jar llegan en las fases 4 y 5.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ServerStateError
from app.core.logging import get_logger
from app.core.paths import sanitize_folder_name, to_folder_slug
from app.models.enums import ServerStatus
from app.models.server import Server
from app.repositories.server_repository import ServerRepository
from app.schemas.server import ServerCreate, ServerUpdate
from app.services.ports import is_port_free

logger = get_logger("servers")

# Campos que exigen reiniciar el servidor: no se tocan mientras está activo.
RESTART_REQUIRED_FIELDS = frozenset({"port", "memory_min_mb", "memory_max_mb"})


class ServerService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ServerRepository(session)

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
        self._session.commit()
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
        logger.info("Servidor actualizado: %s (%s)", server.name, ", ".join(sorted(changes)))
        return server

    def delete_server(self, server_id: int) -> None:
        server = self.get_server(server_id)
        if server.status.is_active:
            raise ServerStateError(
                "Detén el servidor antes de eliminarlo.",
                details={"status": server.status},
            )
        # La carpeta del servidor se eliminará en la fase 4, cuando exista.
        self._repository.delete(server)
        self._session.commit()
        logger.info("Servidor eliminado: %s", server.name)

    def _unique_folder(self, name: str) -> str:
        base = to_folder_slug(name)
        candidate = base
        suffix = 2
        while self._repository.get_by_folder(candidate) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate
