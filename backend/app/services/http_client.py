"""Acceso HTTP saliente: JSON y descargas con progreso y verificación.

Único módulo que habla con servicios externos (Mojang, PaperMC, Purpur,
Fabric, Adoptium). Centralizarlo permite fijar tiempos de espera coherentes y
verificar la integridad de todo lo descargado en un solo sitio.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger("downloads")

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
_HEADERS = {"User-Agent": "MinecraftServerManager/0.1 (+local app)"}

# Firma: (bytes_descargados, bytes_totales | None)
ProgressCallback = Callable[[int, int | None], None]


def get_json(url: str) -> object:
    try:
        response = httpx.get(url, timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise ExternalServiceError(
            "No se pudo consultar un servicio externo.", details={"url": url}
        ) from error


def download_file(
    url: str,
    destination: Path,
    *,
    sha256: str | None = None,
    sha1: str | None = None,
    md5: str | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    """Descarga ``url`` en ``destination`` verificando el hash disponible.

    Se escribe primero en ``<destino>.part`` y sólo se renombra al final: si la
    descarga se corta nunca queda un fichero aparentemente válido a medias.
    """
    algorithms = [
        (name, expected.lower())
        for name, expected in (("sha256", sha256), ("sha1", sha1), ("md5", md5))
        if expected
    ]
    hashers = {name: hashlib.new(name) for name, _ in algorithms}

    partial = destination.with_suffix(destination.suffix + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream(
            "GET", url, timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
        ) as response:
            response.raise_for_status()
            total = (
                int(response.headers["Content-Length"])
                if "Content-Length" in response.headers
                else None
            )
            downloaded = 0
            with partial.open("wb") as file:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    file.write(chunk)
                    downloaded += len(chunk)
                    for hasher in hashers.values():
                        hasher.update(chunk)
                    if progress is not None:
                        progress(downloaded, total)
    except httpx.HTTPError as error:
        partial.unlink(missing_ok=True)
        raise ExternalServiceError(
            "La descarga falló o se interrumpió.", details={"url": url}
        ) from error

    for name, expected in algorithms:
        actual = hashers[name].hexdigest()
        if actual != expected:
            partial.unlink(missing_ok=True)
            raise ExternalServiceError(
                "El fichero descargado no supera la verificación de integridad.",
                details={"url": url, "algorithm": name, "expected": expected, "actual": actual},
            )

    partial.replace(destination)
    logger.info("Descargado %s (%d bytes) en %s", url, destination.stat().st_size, destination)
    return destination
