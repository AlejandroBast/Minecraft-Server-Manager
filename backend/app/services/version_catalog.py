"""Catálogos de versiones y resolución de descargas por tipo de servidor.

Fuentes (comprobadas contra las APIs vivas):
    vanilla  manifest de Mojang (incluye el Java requerido por versión)
    paper    Fill v3 de PaperMC (la API v2 devuelve 410)
    purpur   api.purpurmc.org v2
    fabric   meta.fabricmc.net v2

Spigot no ofrece descargas (exige compilar con BuildTools) y Forge/NeoForge
distribuyen un instalador que hay que ejecutar: su automatización llega en la
fase 8. ``SUPPORT_NOTES`` documenta el motivo hacia la interfaz.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ServerType
from app.services.http_client import get_json

MOJANG_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_API = "https://fill.papermc.io/v3/projects/paper"
PURPUR_API = "https://api.purpurmc.org/v2/purpur"
FABRIC_META = "https://meta.fabricmc.net/v2/versions"

DOWNLOADABLE_TYPES = frozenset(
    {ServerType.VANILLA, ServerType.PAPER, ServerType.PURPUR, ServerType.FABRIC}
)

SUPPORT_NOTES: dict[ServerType, str] = {
    ServerType.SPIGOT: (
        "Spigot no publica descargas directas (exige compilar con BuildTools). "
        "Paper es compatible con sus plugins y sí se descarga automáticamente."
    ),
    ServerType.FORGE: (
        "Forge se distribuye como instalador que hay que ejecutar; "
        "su instalación automática llega con la gestión de mods (fase 8)."
    ),
    ServerType.NEOFORGE: (
        "NeoForge se distribuye como instalador que hay que ejecutar; "
        "su instalación automática llega con la gestión de mods (fase 8)."
    ),
}

_PRERELEASE_MARKS = re.compile(r"(-pre|-rc|-snapshot|snapshot|\dw\d)", re.IGNORECASE)
_DEFAULT_JAVA_MAJOR = 21
_CACHE_TTL_SECONDS = 600.0

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, loader) -> object:  # noqa: ANN001
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now - entry[0] < _CACHE_TTL_SECONDS:
            return entry[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)
    return value


@dataclass(frozen=True)
class VersionInfo:
    version: str
    stable: bool


@dataclass(frozen=True)
class JarDownload:
    url: str
    build: str | None = None
    sha256: str | None = None
    sha1: str | None = None
    md5: str | None = None


def _mojang_manifest() -> dict:
    return _cached("mojang_manifest", lambda: get_json(MOJANG_MANIFEST_URL))  # type: ignore[return-value]


def _mojang_version_meta(version: str) -> dict | None:
    manifest = _mojang_manifest()
    entry = next((item for item in manifest["versions"] if item["id"] == version), None)
    if entry is None:
        return None
    return _cached(f"mojang_meta:{version}", lambda: get_json(entry["url"]))  # type: ignore[return-value]


def required_java_major(version: str) -> int:
    """Java que exige una versión de Minecraft, según la propia Mojang.

    Paper, Purpur y Fabric siguen las versiones del juego, así que el dato de
    Mojang vale para todos. Si la versión no aparece (o la red falla), se usa
    un valor moderno por defecto en lugar de bloquear la instalación.
    """
    try:
        meta = _mojang_version_meta(version)
    except ExternalServiceError:
        return _DEFAULT_JAVA_MAJOR
    if meta is None:
        return _DEFAULT_JAVA_MAJOR
    major = meta.get("javaVersion", {}).get("majorVersion")
    return int(major) if major else _DEFAULT_JAVA_MAJOR


def list_versions(server_type: ServerType) -> list[VersionInfo]:
    """Versiones disponibles, de la más nueva a la más antigua."""
    if server_type is ServerType.VANILLA:
        manifest = _mojang_manifest()
        return [
            VersionInfo(version=item["id"], stable=item["type"] == "release")
            for item in manifest["versions"]
        ]

    if server_type is ServerType.PAPER:
        data = _cached("paper_versions", lambda: get_json(PAPER_API))
        versions: list[VersionInfo] = []
        for family_versions in data["versions"].values():  # type: ignore[index]
            versions.extend(
                VersionInfo(version=version, stable=not _PRERELEASE_MARKS.search(version))
                for version in family_versions
            )
        return versions

    if server_type is ServerType.PURPUR:
        data = _cached("purpur_versions", lambda: get_json(PURPUR_API))
        ordered = list(reversed(data["versions"]))  # type: ignore[index]  # la API lista ascendente
        return [
            VersionInfo(version=version, stable=not _PRERELEASE_MARKS.search(version))
            for version in ordered
        ]

    if server_type is ServerType.FABRIC:
        data = _cached("fabric_game", lambda: get_json(f"{FABRIC_META}/game"))
        return [
            VersionInfo(version=item["version"], stable=bool(item["stable"]))
            for item in data  # type: ignore[union-attr]
        ]

    return []


def resolve_jar(server_type: ServerType, version: str) -> JarDownload:
    """URL y hash del server.jar para un tipo y versión concretos."""
    if server_type not in DOWNLOADABLE_TYPES:
        raise ValidationError(
            SUPPORT_NOTES.get(server_type, "Este tipo de servidor aún no se descarga solo."),
            details={"type": server_type},
        )

    if server_type is ServerType.VANILLA:
        meta = _mojang_version_meta(version)
        if meta is None or "server" not in meta.get("downloads", {}):
            raise ValidationError(
                f"Mojang no publica server.jar para la versión {version}.",
                details={"version": version},
            )
        server = meta["downloads"]["server"]
        return JarDownload(url=server["url"], sha1=server["sha1"])

    if server_type is ServerType.PAPER:
        build = get_json(f"{PAPER_API}/versions/{version}/builds/latest")
        download = build["downloads"]["server:default"]  # type: ignore[index]
        return JarDownload(
            url=download["url"],
            build=str(build["id"]),  # type: ignore[index]
            sha256=download["checksums"]["sha256"],
        )

    if server_type is ServerType.PURPUR:
        detail = get_json(f"{PURPUR_API}/{version}/latest")
        build = str(detail["build"])  # type: ignore[index]
        return JarDownload(
            url=f"{PURPUR_API}/{version}/{build}/download",
            build=build,
            md5=detail.get("md5"),  # type: ignore[union-attr]
        )

    # Fabric: el "server launcher" empaqueta loader + juego. Fabric no publica
    # hashes para este artefacto; la descarga va por HTTPS y sin verificación.
    loaders = get_json(f"{FABRIC_META}/loader")
    installers = get_json(f"{FABRIC_META}/installer")
    loader = next((item["version"] for item in loaders if item.get("stable")), None)  # type: ignore[union-attr]
    installer = next((item["version"] for item in installers if item.get("stable")), None)  # type: ignore[union-attr]
    if not loader or not installer:
        raise ExternalServiceError("Fabric no ofrece loader o installer estables ahora mismo.")
    return JarDownload(
        url=f"{FABRIC_META}/loader/{version}/{loader}/{installer}/server/jar",
        build=loader,
    )
