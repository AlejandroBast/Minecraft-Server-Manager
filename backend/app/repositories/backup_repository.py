"""Acceso a datos de las copias de seguridad."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backup import Backup


class BackupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_server(self, server_id: int) -> Sequence[Backup]:
        statement = (
            select(Backup).where(Backup.server_id == server_id).order_by(Backup.created_at.desc())
        )
        return self._session.scalars(statement).all()

    def get(self, backup_id: int) -> Backup | None:
        return self._session.get(Backup, backup_id)

    def add(self, backup: Backup) -> Backup:
        self._session.add(backup)
        self._session.flush()
        return backup

    def delete(self, backup: Backup) -> None:
        self._session.delete(backup)
        self._session.flush()
