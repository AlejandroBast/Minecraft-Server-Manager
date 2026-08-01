"""Preferencias de la aplicación persistidas como pares clave/valor.

Se guardan en BD (y no en un JSON) para que la UI pueda modificarlas de forma
transaccional y sin condiciones de carrera con el backend en marcha.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Configuration(Base, TimestampMixin):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Configuration key={self.key!r}>"
