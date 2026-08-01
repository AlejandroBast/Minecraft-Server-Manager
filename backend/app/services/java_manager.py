"""Gestión de runtimes de Java (Temurin, vía la API de Adoptium).

El usuario nunca instala Java: cuando una versión de Minecraft exige un major
que no está disponible, se descarga el JRE de Temurin, se verifica su sha256 y
se extrae en ``downloads/java/temurin-<major>/``.
"""

from __future__ import annotations

import platform
import shutil
import zipfile
from pathlib import Path

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.services.http_client import ProgressCallback, download_file, get_json

logger = get_logger("downloads")

ADOPTIUM_API = "https://api.adoptium.net/v3/assets/latest/{major}/hotspot"


def _java_executable(runtime_dir: Path) -> Path:
    name = "java.exe" if platform.system() == "Windows" else "java"
    return runtime_dir / "bin" / name


class JavaManager:
    def __init__(self, java_dir: Path) -> None:
        self._java_dir = java_dir

    def runtime_dir(self, major: int) -> Path:
        return self._java_dir / f"temurin-{major}"

    def find_runtime(self, major: int) -> Path | None:
        """Ruta del ejecutable si el runtime ya está instalado."""
        executable = _java_executable(self.runtime_dir(major))
        return executable if executable.is_file() else None

    def installed_runtimes(self) -> dict[int, Path]:
        runtimes: dict[int, Path] = {}
        if not self._java_dir.exists():
            return runtimes
        for child in sorted(self._java_dir.glob("temurin-*")):
            try:
                major = int(child.name.removeprefix("temurin-"))
            except ValueError:
                continue
            executable = _java_executable(child)
            if executable.is_file():
                runtimes[major] = executable
        return runtimes

    def ensure_runtime(self, major: int, progress: ProgressCallback | None = None) -> Path:
        """Devuelve el java.exe del major pedido, descargándolo si hace falta."""
        existing = self.find_runtime(major)
        if existing is not None:
            return existing

        architecture = "x64" if platform.machine().endswith("64") else "x86"
        system = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}.get(
            platform.system(), "windows"
        )
        url = (
            ADOPTIUM_API.format(major=major)
            + f"?architecture={architecture}&image_type=jre&os={system}&vendor=eclipse"
        )
        assets = get_json(url)
        if not isinstance(assets, list) or not assets:
            raise ExternalServiceError(
                f"Adoptium no ofrece un JRE de Java {major} para este sistema.",
                details={"major": major},
            )
        package = assets[0]["binary"]["package"]

        archive = self._java_dir / package["name"]
        logger.info("Descargando Temurin %d: %s", major, package["name"])
        download_file(package["link"], archive, sha256=package["checksum"], progress=progress)

        extract_dir = self._java_dir / f".extract-{major}"
        shutil.rmtree(extract_dir, ignore_errors=True)
        try:
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extract_dir)

            # El zip contiene una única carpeta raíz (p. ej. jdk-21.0.12+8-jre).
            roots = [child for child in extract_dir.iterdir() if child.is_dir()]
            if len(roots) != 1 or not _java_executable(roots[0]).is_file():
                raise ExternalServiceError(
                    "El paquete de Java descargado no tiene la estructura esperada.",
                    details={"package": package["name"]},
                )
            target = self.runtime_dir(major)
            shutil.rmtree(target, ignore_errors=True)
            roots[0].replace(target)
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)
            archive.unlink(missing_ok=True)

        executable = _java_executable(self.runtime_dir(major))
        logger.info("Temurin %d instalado en %s", major, executable)
        return executable
