"""Creación del esquema y valores por defecto.

En esta fase se usa ``create_all``. Cuando el esquema empiece a evolucionar en
producción se introducirá Alembic sin cambiar este punto de entrada.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import engine, session_scope
from app.models import Configuration

logger = get_logger("app")

DEFAULT_CONFIGURATIONS: dict[str, str] = {
    "language": "es",
    "theme": "dark",
    "servers_dir": str(settings.servers_dir),
    "backups_dir": str(settings.backups_dir),
    "java_dir": str(settings.java_dir),
    "auto_accept_eula": "true",
    "upnp_enabled": "true",
}


def init_db() -> None:
    settings.database_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        existing = {row.key for row in session.query(Configuration.key).all()}
        missing = [
            Configuration(key=key, value=value)
            for key, value in DEFAULT_CONFIGURATIONS.items()
            if key not in existing
        ]
        if missing:
            session.add_all(missing)
            logger.info("Configuración inicial creada: %d claves", len(missing))

    logger.info("Base de datos lista en %s", settings.database_path)
