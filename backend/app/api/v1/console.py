"""Consola de servidores: arranque, parada, comandos y salida en vivo.

La salida se ofrece de dos formas: REST con índice incremental (histórico y
sondeo) y WebSocket (streaming para la interfaz). El WebSocket sólo emite; los
comandos entran siempre por POST, donde pasan por la validación normal.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, status

from app.api.deps import DbSession
from app.schemas.console import ConsoleCommand, ConsoleCommandResult, ConsoleLine, ConsoleOutput
from app.services.process_manager import manager
from app.services.server_service import ServerService

router = APIRouter(prefix="/servers", tags=["console"])

_WS_POLL_SECONDS = 0.4


@router.post("/{server_id}/start", status_code=status.HTTP_202_ACCEPTED)
def start_server(server_id: int, db: DbSession) -> dict[str, str]:
    server = ServerService(db).get_server(server_id)
    db.expunge(server)  # el hilo lector actualizará la fila por su cuenta
    manager.start(server)
    return {"status": "starting"}


@router.post("/{server_id}/stop", status_code=status.HTTP_202_ACCEPTED)
def stop_server(server_id: int, db: DbSession, background_tasks: BackgroundTasks) -> dict[str, str]:
    ServerService(db).get_server(server_id)
    # stop espera hasta 30 s a que el servidor guarde: mejor en segundo plano.
    background_tasks.add_task(manager.stop, server_id)
    return {"status": "stopping"}


@router.post("/{server_id}/restart", status_code=status.HTTP_202_ACCEPTED)
def restart_server(
    server_id: int, db: DbSession, background_tasks: BackgroundTasks
) -> dict[str, str]:
    server = ServerService(db).get_server(server_id)
    db.expunge(server)
    background_tasks.add_task(manager.restart, server)
    return {"status": "restarting"}


@router.get("/{server_id}/console", response_model=ConsoleOutput)
def console_output(server_id: int, db: DbSession, since: int = 0) -> ConsoleOutput:
    ServerService(db).get_server(server_id)
    lines, next_index = manager.output_since(server_id, since)
    return ConsoleOutput(
        lines=[ConsoleLine(index=i, line=line) for i, line in lines],
        next_index=next_index,
        running=manager.is_running(server_id),
    )


@router.post("/{server_id}/console", response_model=ConsoleCommandResult)
def send_command(server_id: int, payload: ConsoleCommand, db: DbSession) -> ConsoleCommandResult:
    ServerService(db).get_server(server_id)
    sent = manager.send_command(server_id, payload.command)
    return ConsoleCommandResult(sent=sent)


@router.websocket("/{server_id}/console/ws")
async def console_stream(websocket: WebSocket, server_id: int) -> None:
    await websocket.accept()
    index = 0
    try:
        while True:
            lines, next_index = manager.output_since(server_id, index)
            for i, line in lines:
                await websocket.send_json({"index": i, "line": line})
            index = max(index, next_index)
            await asyncio.sleep(_WS_POLL_SECONDS)
    except WebSocketDisconnect:
        return
