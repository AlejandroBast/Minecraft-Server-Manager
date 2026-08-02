"""Pruebas de plugins y mods: subida, activación, borrado y catálogos Forge."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.version_catalog import neoforge_to_minecraft

PAPER = {"name": "Con Plugins", "type": "paper", "version": "1.21.4", "port": 25597}


def _create(client: TestClient) -> dict:
    return client.post("/api/v1/servers", json=PAPER).json()["server"]


def _upload(client: TestClient, server_id: int, name: str, content: bytes = b"PK\x03\x04jar"):
    return client.post(
        f"/api/v1/servers/{server_id}/addons/plugins",
        files={"file": (name, io.BytesIO(content), "application/java-archive")},
    )


def test_subir_listar_desactivar_eliminar(client: TestClient) -> None:
    server = _create(client)
    folder = get_settings().servers_dir / server["folder"] / "plugins"

    response = _upload(client, server["id"], "EssentialsX-2.21.jar")
    assert response.status_code == 201, response.text
    assert response.json() == {
        "file": "EssentialsX-2.21.jar",
        "size_bytes": 7,
        "enabled": True,
    }
    assert (folder / "EssentialsX-2.21.jar").is_file()

    listado = client.get(f"/api/v1/servers/{server['id']}/addons/plugins").json()
    assert [item["file"] for item in listado] == ["EssentialsX-2.21.jar"]

    # Desactivar renombra, no borra.
    response = client.patch(
        f"/api/v1/servers/{server['id']}/addons/plugins/EssentialsX-2.21.jar",
        json={"enabled": False},
    )
    assert response.status_code == 200
    assert not (folder / "EssentialsX-2.21.jar").exists()
    assert (folder / "EssentialsX-2.21.jar.disabled").is_file()

    listado = client.get(f"/api/v1/servers/{server['id']}/addons/plugins").json()
    assert listado[0]["enabled"] is False

    # Reactivar y eliminar.
    client.patch(
        f"/api/v1/servers/{server['id']}/addons/plugins/EssentialsX-2.21.jar",
        json={"enabled": True},
    )
    assert (folder / "EssentialsX-2.21.jar").is_file()

    response = client.delete(
        f"/api/v1/servers/{server['id']}/addons/plugins/EssentialsX-2.21.jar"
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/servers/{server['id']}/addons/plugins").json() == []


def test_nombres_peligrosos_se_rechazan(client: TestClient) -> None:
    server = _create(client)
    for malo in ("virus.exe", "..jar", "con.jar", ".jar"):
        response = _upload(client, server["id"], malo)
        assert response.status_code in {403, 422}, malo

    # Un nombre con ruta se reduce a su nombre base (comportamiento de navegadores).
    response = _upload(client, server["id"], "C:\\Users\\yo\\Descargas\\Mod Bueno.jar")
    assert response.status_code == 201
    assert response.json()["file"] == "Mod Bueno.jar"


def test_subida_duplicada_da_409(client: TestClient) -> None:
    server = _create(client)
    assert _upload(client, server["id"], "worldedit.jar").status_code == 201
    assert _upload(client, server["id"], "worldedit.jar").status_code == 409


def test_mods_en_servidor_paper_se_rechaza(client: TestClient) -> None:
    server = _create(client)
    response = client.get(f"/api/v1/servers/{server['id']}/addons/mods")
    assert response.status_code == 409
    assert "no usa mods" in response.json()["message"]


def test_mapa_neoforge_a_minecraft() -> None:
    assert neoforge_to_minecraft("21.1.248") == "1.21.1"
    assert neoforge_to_minecraft("21.4.154") == "1.21.4"
    assert neoforge_to_minecraft("26.1.2.94") == "26.1.2"
    assert neoforge_to_minecraft("26.2.0.41-beta") == "26.2"
    assert neoforge_to_minecraft("20.2.0") == "1.20.2"
    assert neoforge_to_minecraft("21.0.167") == "1.21"
    assert neoforge_to_minecraft("raro") is None


def test_spigot_sigue_sin_descarga(client: TestClient) -> None:
    body = client.get("/api/v1/downloads/versions/spigot").json()
    assert body["supported"] is False
