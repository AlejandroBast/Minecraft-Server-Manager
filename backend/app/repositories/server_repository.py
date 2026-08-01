"""Acceso a datos de servidores. Ningún servicio escribe SQL directamente."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ServerStatus
from app.models.server import Server


class ServerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> Sequence[Server]:
        return self._session.scalars(select(Server).order_by(Server.created_at)).all()

    def get(self, server_id: int) -> Server | None:
        return self._session.get(Server, server_id)

    def get_by_name(self, name: str) -> Server | None:
        statement = select(Server).where(func.lower(Server.name) == name.lower())
        return self._session.scalars(statement).first()

    def get_by_folder(self, folder: str) -> Server | None:
        return self._session.scalars(select(Server).where(Server.folder == folder)).first()

    def get_by_port(self, port: int, exclude_id: int | None = None) -> Server | None:
        statement = select(Server).where(Server.port == port)
        if exclude_id is not None:
            statement = statement.where(Server.id != exclude_id)
        return self._session.scalars(statement).first()

    def count_by_status(self, status: ServerStatus) -> int:
        statement = select(func.count()).select_from(Server).where(Server.status == status)
        return self._session.scalar(statement) or 0

    def add(self, server: Server) -> Server:
        self._session.add(server)
        self._session.flush()
        return server

    def delete(self, server: Server) -> None:
        self._session.delete(server)
        self._session.flush()
