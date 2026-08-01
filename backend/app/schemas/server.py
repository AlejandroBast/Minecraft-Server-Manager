"""Esquemas de entrada y salida de servidores.

La validación de formato vive aquí (borde de la API). Las reglas que necesitan
consultar la base de datos —nombre repetido, puerto ocupado— viven en el
servicio, porque son reglas de negocio y no de formato.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.enums import Difficulty, GameMode, ServerStatus, ServerType

MIN_PORT = 1024
MAX_PORT = 65535
MIN_MEMORY_MB = 512
MAX_MEMORY_MB = 131072


class ServerBase(BaseModel):
    port: int = Field(default=25565, ge=MIN_PORT, le=MAX_PORT)
    max_players: int = Field(default=20, ge=1, le=1000)
    motd: str = Field(default="A Minecraft Server", max_length=120)
    difficulty: Difficulty = Difficulty.NORMAL
    gamemode: GameMode = GameMode.SURVIVAL
    online_mode: bool = True
    hardcore: bool = False
    allow_commands: bool = True
    whitelist_enabled: bool = False
    generate_world: bool = True
    seed: str | None = Field(default=None, max_length=64)
    memory_min_mb: int = Field(default=1024, ge=MIN_MEMORY_MB, le=MAX_MEMORY_MB)
    memory_max_mb: int = Field(default=2048, ge=MIN_MEMORY_MB, le=MAX_MEMORY_MB)

    @model_validator(mode="after")
    def _check_memory(self) -> ServerBase:
        if self.memory_max_mb < self.memory_min_mb:
            raise ValueError("La memoria máxima no puede ser menor que la mínima.")
        return self


class ServerCreate(ServerBase):
    name: str = Field(min_length=2, max_length=50)
    type: ServerType
    version: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._+\-]+$")
    build: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9._+\-]+$")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _check_hardcore(self) -> ServerCreate:
        if self.hardcore and self.difficulty is not Difficulty.HARD:
            # Minecraft fuerza dificultad difícil en hardcore; se corrige en silencio
            # para no rechazar el formulario por algo que el juego ya impone.
            self.difficulty = Difficulty.HARD
        return self


class ServerUpdate(BaseModel):
    """Todos los campos son opcionales: es un PATCH."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=50)
    port: int | None = Field(default=None, ge=MIN_PORT, le=MAX_PORT)
    max_players: int | None = Field(default=None, ge=1, le=1000)
    motd: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty | None = None
    gamemode: GameMode | None = None
    online_mode: bool | None = None
    hardcore: bool | None = None
    allow_commands: bool | None = None
    whitelist_enabled: bool | None = None
    seed: str | None = Field(default=None, max_length=64)
    memory_min_mb: int | None = Field(default=None, ge=MIN_MEMORY_MB, le=MAX_MEMORY_MB)
    memory_max_mb: int | None = Field(default=None, ge=MIN_MEMORY_MB, le=MAX_MEMORY_MB)

    @model_validator(mode="after")
    def _check_memory(self) -> ServerUpdate:
        if (
            self.memory_min_mb is not None
            and self.memory_max_mb is not None
            and self.memory_max_mb < self.memory_min_mb
        ):
            raise ValueError("La memoria máxima no puede ser menor que la mínima.")
        return self


class ServerRead(ServerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    folder: str
    type: ServerType
    version: str
    build: str | None
    status: ServerStatus
    java_path: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def supports_plugins(self) -> bool:
        return self.type.supports_plugins

    @computed_field
    @property
    def supports_mods(self) -> bool:
        return self.type.supports_mods


class ServerCreated(BaseModel):
    """Respuesta de creación: el servidor más los avisos que no lo impidieron."""

    server: ServerRead
    warnings: list[str] = Field(default_factory=list)
