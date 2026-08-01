"""Acceso a las preferencias clave/valor de la aplicación."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import Configuration


class ConfigurationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def all_as_dict(self) -> dict[str, str | None]:
        rows = self._session.scalars(select(Configuration).order_by(Configuration.key)).all()
        return {row.key: row.value for row in rows}

    def get(self, key: str) -> Configuration | None:
        return self._session.scalars(
            select(Configuration).where(Configuration.key == key)
        ).first()

    def set(self, key: str, value: str | None) -> Configuration:
        existing = self.get(key)
        if existing is None:
            existing = Configuration(key=key, value=value)
            self._session.add(existing)
        else:
            existing.value = value
        self._session.flush()
        return existing
