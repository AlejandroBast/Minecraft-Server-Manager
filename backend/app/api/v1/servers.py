"""Endpoints REST de servidores."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import DbSession
from app.core.exceptions import NotFoundError, ServerStateError
from app.models.enums import ServerStatus
from app.schemas.downloads import InstallProgressRead
from app.schemas.server import ServerCreate, ServerCreated, ServerRead, ServerUpdate
from app.schemas.stats import ServerStatsRead
from app.services import stats_service
from app.services.download_service import run_full_install
from app.services.install_tracker import tracker
from app.services.process_manager import manager
from app.services.server_service import ServerService

router = APIRouter(prefix="/servers", tags=["servers"])


def _with_uptime(server) -> ServerRead:  # noqa: ANN001
    read = ServerRead.model_validate(server)
    read.uptime_seconds = manager.uptime_seconds(server.id)
    return read


@router.get("", response_model=list[ServerRead])
def list_servers(db: DbSession) -> list[ServerRead]:
    servers = ServerService(db).list_servers()
    return [_with_uptime(server) for server in servers]


@router.post("", response_model=ServerCreated, status_code=status.HTTP_201_CREATED)
def create_server(
    payload: ServerCreate, db: DbSession, background_tasks: BackgroundTasks
) -> ServerCreated:
    server, warnings = ServerService(db).create_server(payload)
    # La descarga de Java y del jar puede tardar minutos: corre en segundo
    # plano y el frontend sigue el avance por /servers/{id}/install.
    background_tasks.add_task(run_full_install, server.id)
    return ServerCreated(server=ServerRead.model_validate(server), warnings=warnings)


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, db: DbSession) -> ServerRead:
    return _with_uptime(ServerService(db).get_server(server_id))


@router.post("/{server_id}/install/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_install(
    server_id: int, db: DbSession, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Reintenta la instalación sin perder el servidor ni su mundo.

    Una descarga cortada (internet, antivirus, cierre de la aplicación) dejaba
    el servidor en un callejón sin salida: no arrancaba y había que borrarlo.
    """
    server = ServerService(db).get_server(server_id)
    if manager.is_running(server.id):
        raise ServerStateError("Detén el servidor antes de reinstalarlo.")
    if server.status is ServerStatus.INSTALLING:
        raise ServerStateError("La instalación ya está en curso.")

    server.status = ServerStatus.INSTALLING
    server.last_error = None
    db.commit()

    tracker.clear(server_id)
    background_tasks.add_task(run_full_install, server_id)
    return {"status": "installing"}


@router.get("/{server_id}/stats", response_model=ServerStatsRead)
def server_stats(server_id: int, db: DbSession) -> ServerStatsRead:
    server = ServerService(db).get_server(server_id)
    return ServerStatsRead.model_validate(stats_service.collect(server))


@router.get("/{server_id}/install", response_model=InstallProgressRead)
def install_progress(server_id: int, db: DbSession) -> InstallProgressRead:
    ServerService(db).get_server(server_id)  # 404 si no existe
    progress = tracker.get(server_id)
    if progress is None:
        raise NotFoundError(
            "No hay ninguna instalación en curso para este servidor.",
            details={"server_id": server_id},
        )
    return InstallProgressRead(
        stage=progress.stage, progress=progress.progress, detail=progress.detail
    )


@router.patch("/{server_id}", response_model=ServerRead)
def update_server(server_id: int, payload: ServerUpdate, db: DbSession) -> ServerRead:
    return ServerRead.model_validate(ServerService(db).update_server(server_id, payload))


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, db: DbSession) -> None:
    ServerService(db).delete_server(server_id)
    stats_service.forget(server_id)
    tracker.clear(server_id)
