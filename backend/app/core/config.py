"""Configuración central de la aplicación.

Todas las rutas del proyecto se derivan de la raíz del repositorio y pueden
sobrescribirse mediante variables de entorno con prefijo ``MSM_`` o el fichero
``.env`` de la raíz. La UI de ajustes (fase 3) escribirá sobre esas mismas
claves, por lo que ningún módulo debe construir rutas por su cuenta.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
PROJECT_ROOT: Path = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Ajustes de la aplicación resueltos en tiempo de arranque."""

    model_config = SettingsConfigDict(
        env_prefix="MSM_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Minecraft Server Manager"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "127.0.0.1"
    port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    # Cualquier puerto de localhost: la interfaz puede acabar en uno distinto
    # del 3000 si ese está ocupado, y debe seguir hablando con la API.
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

    project_root: Path = PROJECT_ROOT
    servers_dir: Path = PROJECT_ROOT / "servers"
    downloads_dir: Path = PROJECT_ROOT / "downloads"
    java_dir: Path = PROJECT_ROOT / "downloads" / "java"
    backups_dir: Path = PROJECT_ROOT / "backups"
    database_dir: Path = PROJECT_ROOT / "database"
    logs_dir: Path = PROJECT_ROOT / "logs"
    config_dir: Path = PROJECT_ROOT / "config"
    temp_dir: Path = PROJECT_ROOT / "temp"

    database_file: str = "manager.db"
    log_level: str = "INFO"
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 5

    @field_validator(
        "project_root",
        "servers_dir",
        "downloads_dir",
        "java_dir",
        "backups_dir",
        "database_dir",
        "logs_dir",
        "config_dir",
        "temp_dir",
        mode="after",
    )
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @property
    def database_path(self) -> Path:
        return self.database_dir / self.database_file

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def managed_dirs(self) -> tuple[Path, ...]:
        """Directorios que la aplicación crea y sobre los que puede escribir."""
        return (
            self.servers_dir,
            self.downloads_dir,
            self.java_dir,
            self.backups_dir,
            self.database_dir,
            self.logs_dir,
            self.config_dir,
            self.temp_dir,
        )

    def ensure_directories(self) -> None:
        for directory in self.managed_dirs:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instancia única de ajustes (cacheada para usarse como dependencia)."""
    return Settings()


settings: Settings = get_settings()
