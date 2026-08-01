"""Operaciones de disco sobre las carpetas de servidores.

Único módulo autorizado a crear y borrar carpetas dentro de ``servers/``.
Toda ruta pasa por el sandbox de ``app.core.paths``: aunque un dato corrupto
llegara hasta aquí, es imposible tocar nada fuera del directorio gestionado.
"""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.paths import resolve_within

logger = get_logger("servers")


def _on_remove_error(func, path, _exc_info) -> None:  # noqa: ANN001
    """Reintenta el borrado quitando el atributo de sólo lectura (Windows)."""
    Path(path).chmod(stat.S_IWRITE)
    func(path)


class ServerFilesystem:
    def __init__(self, servers_dir: Path) -> None:
        self._servers_dir = servers_dir

    def path_of(self, folder: str) -> Path:
        """Ruta absoluta y validada de la carpeta de un servidor."""
        return resolve_within(self._servers_dir, folder)

    def exists(self, folder: str) -> bool:
        return self.path_of(folder).exists()

    def create_layout(self, folder: str, *, plugins: bool, mods: bool) -> Path:
        """Crea la estructura base del servidor y devuelve su raíz."""
        root = self.path_of(folder)
        if root.exists():
            raise ConflictError(
                "La carpeta del servidor ya existe en disco.", details={"folder": folder}
            )

        subdirs = ["logs", "world"]
        if plugins:
            subdirs.append("plugins")
        if mods:
            subdirs.append("mods")

        root.mkdir(parents=True)
        for subdir in subdirs:
            (root / subdir).mkdir()
        logger.info("Estructura creada en %s", root)
        return root

    def write_file(self, folder: str, relative: str, content: str) -> Path:
        """Escribe un fichero de texto dentro de la carpeta del servidor."""
        target = resolve_within(self.path_of(folder), relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return target

    def remove(self, folder: str, *, missing_ok: bool = False) -> None:
        """Elimina por completo la carpeta de un servidor."""
        root = self.path_of(folder)
        if not root.exists():
            if missing_ok:
                return
            raise NotFoundError(
                "La carpeta del servidor no existe en disco.", details={"folder": folder}
            )
        shutil.rmtree(root, onexc=_on_remove_error)
        logger.info("Carpeta eliminada: %s", root)

    def size_bytes(self, folder: str) -> int:
        """Tamaño total en bytes del contenido del servidor."""
        root = self.path_of(folder)
        if not root.exists():
            return 0
        return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())
