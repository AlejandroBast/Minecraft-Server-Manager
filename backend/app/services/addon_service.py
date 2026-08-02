"""Gestión de plugins y mods: listar, subir, activar/desactivar y eliminar.

Los jar se **adjuntan desde la interfaz** (subida multipart): el usuario nunca
tiene que abrir la carpeta del servidor. Desactivar no borra nada: renombra a
``.jar.disabled``, que los cargadores ignoran, y puede revertirse con un clic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.paths import resolve_within
from app.models.server import Server
from app.services.server_service import ServerService

logger = get_logger("servers")

DISABLED_SUFFIX = ".disabled"
MAX_ADDON_BYTES = 200 * 1024 * 1024  # los modpacks grandes rondan 100 MB
_SAFE_JAR_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+\-\[\]()]{0,118}\.jar$", re.IGNORECASE)
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class AddonKind(StrEnum):
    PLUGINS = "plugins"
    MODS = "mods"


@dataclass(frozen=True)
class AddonInfo:
    file: str
    size_bytes: int
    enabled: bool


class AddonService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._servers = ServerService(session, self._settings)

    def _folder(self, server: Server, kind: AddonKind) -> Path:
        supported = (
            server.type.supports_plugins if kind is AddonKind.PLUGINS else server.type.supports_mods
        )
        if not supported:
            raise ConflictError(
                f"Un servidor {server.type.value} no usa {kind.value}.",
                details={"type": server.type, "kind": kind},
            )
        folder = resolve_within(self._settings.servers_dir / server.folder, kind.value)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def list_addons(self, server_id: int, kind: AddonKind) -> list[AddonInfo]:
        server = self._servers.get_server(server_id)
        folder = self._folder(server, kind)
        addons: list[AddonInfo] = []
        for item in sorted(folder.iterdir()):
            if not item.is_file():
                continue
            name = item.name
            if name.lower().endswith(".jar"):
                addons.append(AddonInfo(file=name, size_bytes=item.stat().st_size, enabled=True))
            elif name.lower().endswith(f".jar{DISABLED_SUFFIX}"):
                addons.append(
                    AddonInfo(
                        file=name.removesuffix(DISABLED_SUFFIX),
                        size_bytes=item.stat().st_size,
                        enabled=False,
                    )
                )
        return addons

    def upload(self, server_id: int, kind: AddonKind, filename: str, stream: BinaryIO) -> AddonInfo:
        server = self._servers.get_server(server_id)
        folder = self._folder(server, kind)

        # Sólo el nombre base: los navegadores pueden mandar rutas completas.
        clean_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if clean_name.split(".")[0].lower() in _WINDOWS_RESERVED or not _SAFE_JAR_NAME.match(
            clean_name
        ):
            raise ValidationError(
                "El archivo debe ser un .jar con un nombre sencillo "
                "(letras, números, espacios, puntos y guiones).",
                details={"filename": filename},
            )

        destination = resolve_within(folder, clean_name)
        if destination.exists() or destination.with_name(
            destination.name + DISABLED_SUFFIX
        ).exists():
            raise ConflictError(
                f"Ya existe «{clean_name}» en {kind.value}; elimínalo primero.",
                details={"filename": clean_name},
            )

        partial = destination.with_suffix(destination.suffix + ".part")
        written = 0
        try:
            with partial.open("wb") as target:
                while chunk := stream.read(1024 * 512):
                    written += len(chunk)
                    if written > MAX_ADDON_BYTES:
                        raise ValidationError(
                            "El archivo supera el límite de 200 MB.",
                            details={"filename": clean_name},
                        )
                    target.write(chunk)
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise

        logger.info("Subido %s/%s (%d bytes) a %s", kind.value, clean_name, written, server.name)
        return AddonInfo(file=clean_name, size_bytes=written, enabled=True)

    def set_enabled(
        self, server_id: int, kind: AddonKind, filename: str, enabled: bool
    ) -> AddonInfo:
        server = self._servers.get_server(server_id)
        folder = self._folder(server, kind)
        active = resolve_within(folder, filename)
        disabled = resolve_within(folder, filename + DISABLED_SUFFIX)

        if enabled and disabled.is_file():
            if active.exists():
                raise ConflictError("Ya existe un jar activo con ese nombre.")
            disabled.replace(active)
        elif not enabled and active.is_file():
            disabled_target = disabled
            active.replace(disabled_target)
        elif not (active.is_file() or disabled.is_file()):
            raise NotFoundError(
                f"No existe «{filename}» en {kind.value}.", details={"filename": filename}
            )

        current = active if enabled else disabled
        logger.info(
            "%s %s/%s en %s", "Activado" if enabled else "Desactivado", kind.value, filename,
            server.name,
        )
        return AddonInfo(file=filename, size_bytes=current.stat().st_size, enabled=enabled)

    def delete(self, server_id: int, kind: AddonKind, filename: str) -> None:
        server = self._servers.get_server(server_id)
        folder = self._folder(server, kind)
        active = resolve_within(folder, filename)
        disabled = resolve_within(folder, filename + DISABLED_SUFFIX)
        if not (active.is_file() or disabled.is_file()):
            raise NotFoundError(
                f"No existe «{filename}» en {kind.value}.", details={"filename": filename}
            )
        active.unlink(missing_ok=True)
        disabled.unlink(missing_ok=True)
        logger.info("Eliminado %s/%s de %s", kind.value, filename, server.name)
