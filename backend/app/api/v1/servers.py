"""Endpoints REST de servidores."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.server import ServerCreate, ServerCreated, ServerRead, ServerUpdate
from app.services.server_service import ServerService

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerRead])
def list_servers(db: DbSession) -> list[ServerRead]:
    servers = ServerService(db).list_servers()
    return [ServerRead.model_validate(server) for server in servers]


@router.post("", response_model=ServerCreated, status_code=status.HTTP_201_CREATED)
def create_server(payload: ServerCreate, db: DbSession) -> ServerCreated:
    server, warnings = ServerService(db).create_server(payload)
    return ServerCreated(server=ServerRead.model_validate(server), warnings=warnings)


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, db: DbSession) -> ServerRead:
    return ServerRead.model_validate(ServerService(db).get_server(server_id))


@router.patch("/{server_id}", response_model=ServerRead)
def update_server(server_id: int, payload: ServerUpdate, db: DbSession) -> ServerRead:
    return ServerRead.model_validate(ServerService(db).update_server(server_id, payload))


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, db: DbSession) -> None:
    ServerService(db).delete_server(server_id)
