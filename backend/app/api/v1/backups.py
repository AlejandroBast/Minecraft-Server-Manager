"""Endpoints de copias de seguridad."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import DbSession
from app.schemas.backup import BackupCreate, BackupRead
from app.services.backup_service import BackupRestorer, BackupService, delete_backup, run_backup

router = APIRouter(tags=["backups"])


@router.get("/servers/{server_id}/backups", response_model=list[BackupRead])
def list_backups(server_id: int, db: DbSession) -> list[BackupRead]:
    backups = BackupService(db).list_backups(server_id)
    return [BackupRead.model_validate(backup) for backup in backups]


@router.post(
    "/servers/{server_id}/backups",
    response_model=BackupRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_backup(
    server_id: int, payload: BackupCreate, db: DbSession, background_tasks: BackgroundTasks
) -> BackupRead:
    backup = BackupService(db).register_backup(server_id, payload.notes)
    # Comprimir un mundo puede tardar: la respuesta vuelve ya con la fila en
    # RUNNING y el estado final se consulta en el listado.
    background_tasks.add_task(run_backup, backup.id)
    return BackupRead.model_validate(backup)


@router.post("/backups/{backup_id}/restore", status_code=status.HTTP_200_OK)
def restore_backup(backup_id: int, db: DbSession) -> dict[str, str]:
    BackupRestorer().restore(db, backup_id)
    return {"status": "restored"}


@router.delete("/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_backup(backup_id: int, db: DbSession) -> None:
    delete_backup(db, backup_id)
