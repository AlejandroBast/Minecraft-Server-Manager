"""Sandbox de rutas: única puerta de acceso al sistema de ficheros.

Ningún módulo debe concatenar rutas recibidas del frontend. Todo acceso pasa
por ``resolve_within``, que normaliza símbolos (``..``, enlaces, unidades) y
verifica que el resultado siga dentro del directorio permitido.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.exceptions import PathTraversalError, ValidationError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,48}[A-Za-z0-9_.\-]$")
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def is_within(base: Path, target: Path) -> bool:
    """``True`` si ``target`` está contenido en ``base`` tras resolverse."""
    try:
        target.resolve().relative_to(base.resolve())
    except (ValueError, OSError):
        return False
    return True


def resolve_within(base: Path, relative: str | Path = "") -> Path:
    """Resuelve ``relative`` dentro de ``base`` o lanza ``PathTraversalError``."""
    relative_path = Path(relative)
    if relative_path.is_absolute() or relative_path.drive:
        raise PathTraversalError("No se permiten rutas absolutas.")

    candidate = (base / relative_path).resolve()
    if not is_within(base, candidate):
        raise PathTraversalError(
            "La ruta solicitada está fuera del directorio permitido.",
            details={"path": str(relative)},
        )
    return candidate


def sanitize_folder_name(name: str) -> str:
    """Valida un nombre de carpeta de servidor generado por el usuario."""
    cleaned = name.strip()
    if not _SAFE_NAME.match(cleaned):
        raise ValidationError(
            "El nombre sólo admite letras, números, espacios, guiones y puntos "
            "(entre 2 y 50 caracteres).",
            details={"name": name},
        )
    if cleaned.split(".")[0].lower() in _WINDOWS_RESERVED:
        raise ValidationError("Ese nombre está reservado por Windows.", details={"name": name})
    return cleaned
