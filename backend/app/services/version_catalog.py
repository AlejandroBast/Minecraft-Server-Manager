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
from app.services.http_client import get_json, get_text

MOJANG_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_API = "https://fill.papermc.io/v3/projects/paper"
PURPUR_API = "https://api.purpurmc.org/v2/purpur"
FABRIC_META = "https://meta.fabricmc.net/v2/versions"
FORGE_PROMOTIONS_URL = (
    "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
)
FORGE_MAVEN = "https://maven.minecraftforge.net/net/minecraftforge/forge"
NEOFORGE_METADATA_URL = (
    "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
)
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"

DOWNLOADABLE_TYPES = frozenset(
    {
        ServerType.VANILLA,
        ServerType.PAPER,
        ServerType.PURPUR,
        ServerType.FABRIC,
        ServerType.FORGE,
        ServerType.NEOFORGE,
    }
)

# Tipos cuya descarga es un instalador que hay que ejecutar, no un server.jar.
INSTALLER_TYPES = frozenset({ServerType.FORGE, ServerType.NEOFORGE})

SUPPORT_NOTES: dict[ServerType, str] = {
    ServerType.SPIGOT: (
        "Spigot no publica descargas directas (exige compilar con BuildTools). "
        "Paper es compatible con sus plugins y sí se descarga automáticamente."
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


def _forge_promotions() -> dict[str, str]:
    data = _cached("forge_promos", lambda: get_json(FORGE_PROMOTIONS_URL))
    return data["promos"]  # type: ignore[index,return-value]


def _neoforge_versions() -> list[str]:
    def load() -> list[str]:
        import xml.etree.ElementTree as ElementTree

        root = ElementTree.fromstring(get_text(NEOFORGE_METADATA_URL))  # noqa: S314 - fuente fija
        return [node.text or "" for node in root.iter("version")]

    return _cached("neoforge_versions", load)  # type: ignore[return-value]


def neoforge_to_minecraft(neoforge_version: str) -> str | None:
    """Versión de Minecraft a la que corresponde una build de NeoForge.

    Esquema antiguo: ``21.1.248`` → MC ``1.21.1``. Esquema nuevo (desde el
    cambio de versionado del juego): ``26.1.2.94`` → MC ``26.1.2`` y
    ``26.2.0.41-beta`` → MC ``26.2``.
    """
    base = neoforge_version.split("-", 1)[0]
    parts = base.split(".")
    if not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]

    if len(numbers) == 3 and numbers[0] < 26:
        minor, patch = numbers[0], numbers[1]
        return f"1.{minor}" if patch == 0 else f"1.{minor}.{patch}"
    if len(numbers) == 4:
        major, minor, patch = numbers[0], numbers[1], numbers[2]
        return f"{major}.{minor}" if patch == 0 else f"{major}.{minor}.{patch}"
    return None


def _maven_sha1(artifact_url: str) -> str | None:
    """Los repositorios Maven publican el sha1 del artefacto junto a él."""
    try:
        return get_text(artifact_url + ".sha1").strip().split()[0]
    except ExternalServiceError:
        return None


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

    if server_type is ServerType.FORGE:
        promos = _forge_promotions()
        seen: dict[str, bool] = {}
        for key in promos:  # el json lista de la más antigua a la más nueva
            mc_version, _, channel = key.rpartition("-")
            if not mc_version:
                continue
            seen[mc_version] = seen.get(mc_version, False) or channel == "recommended"
        return [
            VersionInfo(version=version, stable=recommended)
            for version, recommended in reversed(list(seen.items()))
        ]

    if server_type is ServerType.NEOFORGE:
        seen_versions: dict[str, bool] = {}
        for nf_version in _neoforge_versions():  # ascendente en el metadata
            mc_version = neoforge_to_minecraft(nf_version)
            if mc_version is None:
                continue
            is_stable = "beta" not in nf_version and "rc" not in nf_version
            seen_versions[mc_version] = seen_versions.get(mc_version, False) or is_stable
        return [
            VersionInfo(version=version, stable=stable)
            for version, stable in reversed(list(seen_versions.items()))
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

    if server_type is ServerType.FABRIC:
        # El "server launcher" empaqueta loader + juego. Fabric no publica
        # hashes para este artefacto; la descarga va por HTTPS sin verificar.
        loaders = get_json(f"{FABRIC_META}/loader")
        installers = get_json(f"{FABRIC_META}/installer")
        loader = next((item["version"] for item in loaders if item.get("stable")), None)  # type: ignore[union-attr]
        installer = next(
            (item["version"] for item in installers if item.get("stable")), None  # type: ignore[union-attr]
        )
        if not loader or not installer:
            raise ExternalServiceError("Fabric no ofrece loader o installer estables ahora mismo.")
        return JarDownload(
            url=f"{FABRIC_META}/loader/{version}/{loader}/{installer}/server/jar",
            build=loader,
        )

    if server_type is ServerType.FORGE:
        promos = _forge_promotions()
        build = promos.get(f"{version}-recommended") or promos.get(f"{version}-latest")
        if not build:
            raise ValidationError(
                f"Forge no publica una build para Minecraft {version}.",
                details={"version": version},
            )
        base = f"{FORGE_MAVEN}/{version}-{build}/forge-{version}-{build}-installer.jar"
        return JarDownload(url=base, build=build, sha1=_maven_sha1(base))

    # NeoForge: se elige la build más nueva (estable si existe) de esa versión.
    candidates = [
        nf for nf in _neoforge_versions() if neoforge_to_minecraft(nf) == version
    ]
    if not candidates:
        raise ValidationError(
            f"NeoForge no publica una build para Minecraft {version}.",
            details={"version": version},
        )
    stable_candidates = [nf for nf in candidates if "beta" not in nf and "rc" not in nf]
    build = (stable_candidates or candidates)[-1]
    url = f"{NEOFORGE_MAVEN}/{build}/neoforge-{build}-installer.jar"
    return JarDownload(url=url, build=build, sha1=_maven_sha1(url))
