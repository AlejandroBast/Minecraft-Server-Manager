"""Configuración de logging por categorías con rotación de ficheros.

Categorías (una por fichero en ``logs/``):
    app        errores generales y ciclo de vida de la API
    servers    inicio, detención y estado de cada servidor
    downloads  descargas de Java, jars y librerías
    console    salida de las consolas de los servidores
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_CATEGORIES: tuple[str, ...] = ("app", "servers", "downloads", "console")

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured = False


def setup_logging(
    logs_dir: Path,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Instala los manejadores. Idempotente: repetirla no duplica salidas."""
    global _configured
    if _configured:
        return

    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)
    resolved_level = getattr(logging, level.upper(), logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(resolved_level)
    root.addHandler(console_handler)

    for category in LOG_CATEGORIES:
        handler = RotatingFileHandler(
            logs_dir / f"{category}.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        category_logger = logging.getLogger(category)
        category_logger.setLevel(resolved_level)
        category_logger.addHandler(handler)

    _configured = True


def get_logger(category: str = "app") -> logging.Logger:
    """Devuelve el logger de una categoría (``app.downloads`` hereda de ``app``)."""
    return logging.getLogger(category)
