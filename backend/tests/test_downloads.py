"""Pruebas del catálogo de versiones y la instalación en segundo plano.

La red se sustituye por respuestas grabadas de las APIs reales: las pruebas
verifican el análisis de cada formato, no la disponibilidad de los servicios.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.version_catalog as catalog
from app.models.enums import ServerType
from app.services.install_tracker import InstallTracker

MOJANG_MANIFEST = {
    "latest": {"release": "26.2"},
    "versions": [
        {"id": "26.3-snapshot-6", "type": "snapshot", "url": "https://mojang/26.3s6.json"},
        {"id": "26.2", "type": "release", "url": "https://mojang/26.2.json"},
        {"id": "1.21.4", "type": "release", "url": "https://mojang/1.21.4.json"},
        {"id": "1.16.5", "type": "release", "url": "https://mojang/1.16.5.json"},
    ],
}
MOJANG_METAS = {
    "https://mojang/26.2.json": {
        "javaVersion": {"majorVersion": 25},
        "downloads": {"server": {"url": "https://mojang/server-26.2.jar", "sha1": "abc"}},
    },
    "https://mojang/1.21.4.json": {
        "javaVersion": {"majorVersion": 21},
        "downloads": {"server": {"url": "https://mojang/server-1.21.4.jar", "sha1": "def"}},
    },
    "https://mojang/1.16.5.json": {
        "javaVersion": {"majorVersion": 8},
        "downloads": {"server": {"url": "https://mojang/server-1.16.5.jar", "sha1": "ghi"}},
    },
}
PAPER_PROJECT = {"versions": {"26.2": ["26.2", "26.2-rc-2"], "1.21": ["1.21.4"]}}
PAPER_BUILD = {
    "id": 87,
    "downloads": {
        "server:default": {
            "name": "paper-26.2-87.jar",
            "checksums": {"sha256": "3ab753"},
            "url": "https://paper/download.jar",
        }
    },
}
PURPUR_VERSIONS = {"versions": ["1.21.4", "26.1", "26.2"]}
PURPUR_LATEST = {"build": "2450", "md5": "aabbcc"}
FABRIC_GAME = [
    {"version": "26.3-snapshot-6", "stable": False},
    {"version": "26.2", "stable": True},
]
FABRIC_LOADER = [{"version": "0.19.3", "stable": True}]
FABRIC_INSTALLER = [{"version": "1.1.2", "stable": True}]


@pytest.fixture(autouse=True)
def catalogo_sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        catalog.MOJANG_MANIFEST_URL: MOJANG_MANIFEST,
        catalog.PAPER_API: PAPER_PROJECT,
        f"{catalog.PAPER_API}/versions/26.2/builds/latest": PAPER_BUILD,
        catalog.PURPUR_API: PURPUR_VERSIONS,
        f"{catalog.PURPUR_API}/26.2/latest": PURPUR_LATEST,
        f"{catalog.FABRIC_META}/game": FABRIC_GAME,
        f"{catalog.FABRIC_META}/loader": FABRIC_LOADER,
        f"{catalog.FABRIC_META}/installer": FABRIC_INSTALLER,
        **MOJANG_METAS,
    }

    def fake_get_json(url: str) -> object:
        assert url in responses, f"petición inesperada en pruebas: {url}"
        return responses[url]

    monkeypatch.setattr(catalog, "get_json", fake_get_json)
    monkeypatch.setattr(catalog, "_cache", {})


def test_vanilla_lista_y_marca_snapshots() -> None:
    versions = catalog.list_versions(ServerType.VANILLA)
    assert versions[0].version == "26.3-snapshot-6"
    assert versions[0].stable is False
    assert versions[1].stable is True


def test_java_requerido_lo_dicta_mojang() -> None:
    assert catalog.required_java_major("26.2") == 25
    assert catalog.required_java_major("1.21.4") == 21
    assert catalog.required_java_major("1.16.5") == 8
    assert catalog.required_java_major("version-desconocida") == 21  # respaldo


def test_resolver_paper_usa_fill_v3() -> None:
    download = catalog.resolve_jar(ServerType.PAPER, "26.2")
    assert download.url == "https://paper/download.jar"
    assert download.build == "87"
    assert download.sha256 == "3ab753"


def test_resolver_purpur_y_orden_descendente() -> None:
    versions = catalog.list_versions(ServerType.PURPUR)
    assert versions[0].version == "26.2"  # la API lista ascendente; se invierte

    download = catalog.resolve_jar(ServerType.PURPUR, "26.2")
    assert download.build == "2450"
    assert download.md5 == "aabbcc"
    assert download.url.endswith("/26.2/2450/download")


def test_resolver_fabric_compone_la_url() -> None:
    download = catalog.resolve_jar(ServerType.FABRIC, "26.2")
    assert download.url.endswith("/loader/26.2/0.19.3/1.1.2/server/jar")


def test_tipos_no_descargables() -> None:
    from app.core.exceptions import ValidationError

    for tipo in (ServerType.SPIGOT, ServerType.FORGE, ServerType.NEOFORGE):
        assert catalog.list_versions(tipo) == []
        with pytest.raises(ValidationError):
            catalog.resolve_jar(tipo, "1.21.4")


def test_endpoint_versiones(client: TestClient) -> None:
    response = client.get("/api/v1/downloads/versions/spigot")
    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is False
    assert "BuildTools" in body["reason"]
    assert body["versions"] == []

    response = client.get("/api/v1/downloads/versions/vanilla")
    assert response.status_code == 200
    assert response.json()["supported"] is True


def test_crear_spigot_se_rechaza_con_motivo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/servers",
        json={"name": "Spigoteado", "type": "spigot", "version": "1.21.4"},
    )
    assert response.status_code == 409
    assert "Paper" in response.json()["message"]


def test_progreso_sin_instalacion_da_404(client: TestClient) -> None:
    created = client.post(
        "/api/v1/servers", json={"name": "Sin Progreso", "type": "paper", "version": "26.2"}
    ).json()["server"]
    response = client.get(f"/api/v1/servers/{created['id']}/install")
    assert response.status_code == 404


def test_tracker_acota_el_progreso() -> None:
    tracker = InstallTracker()
    tracker.update(1, "jar", 1.7, "x")
    assert tracker.get(1).progress == 1.0
    tracker.update(1, "jar", -0.3, "x")
    assert tracker.get(1).progress == 0.0
    tracker.clear(1)
    assert tracker.get(1) is None
