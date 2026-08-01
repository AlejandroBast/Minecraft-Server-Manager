"""Modelo de servidor de Minecraft.

Guarda tanto los metadatos de gestión (estado, carpeta, proceso) como la
configuración elegida en el formulario de creación, que es la fuente de verdad
para regenerar ``server.properties`` sin que el usuario edite ficheros.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import Difficulty, GameMode, ServerStatus, ServerType

if TYPE_CHECKING:
    from app.models.backup import Backup


class Server(Base, TimestampMixin):
    __tablename__ = "servers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_servers_name"),
        UniqueConstraint("folder", name="uq_servers_folder"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    folder: Mapped[str] = mapped_column(String(255), nullable=False)

    type: Mapped[ServerType] = mapped_column(
        Enum(ServerType, native_enum=False, length=20), nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    build: Mapped[str | None] = mapped_column(String(32))
    jar_file: Mapped[str | None] = mapped_column(String(255))
    java_path: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[ServerStatus] = mapped_column(
        Enum(ServerStatus, native_enum=False, length=20),
        nullable=False,
        default=ServerStatus.STOPPED,
    )
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=25565)
    memory_min_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    memory_max_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=2048)

    max_players: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    motd: Mapped[str] = mapped_column(String(120), nullable=False, default="A Minecraft Server")
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, native_enum=False, length=16), nullable=False, default=Difficulty.NORMAL
    )
    gamemode: Mapped[GameMode] = mapped_column(
        Enum(GameMode, native_enum=False, length=16), nullable=False, default=GameMode.SURVIVAL
    )
    online_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hardcore: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_commands: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    whitelist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generate_world: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seed: Mapped[str | None] = mapped_column(String(64))

    last_error: Mapped[str | None] = mapped_column(Text)

    backups: Mapped[list["Backup"]] = relationship(
        back_populates="server", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Server id={self.id} name={self.name!r} status={self.status}>"
