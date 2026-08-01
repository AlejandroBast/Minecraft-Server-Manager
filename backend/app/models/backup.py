"""Modelo de copia de seguridad de un servidor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import BackupStatus

if TYPE_CHECKING:
    from app.models.server import Server


class Backup(Base, TimestampMixin):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, native_enum=False, length=16),
        nullable=False,
        default=BackupStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    server: Mapped["Server"] = relationship(back_populates="backups")

    def __repr__(self) -> str:
        return f"<Backup id={self.id} server_id={self.server_id} file={self.file!r}>"
