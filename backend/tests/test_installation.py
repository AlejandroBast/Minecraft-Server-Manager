"""Pruebas de la instalación en disco de los servidores (fase 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import PathTraversalError
from app.services.filesystem import ServerFilesystem
from app.services.properties_writer import escape_properties_value

BASE_PAYLOAD = {
    "name": "Servidor Disco",
    "type": "paper",
    "version": "1.21.4",
    "port": 25580,
    "max_players": 10,
    "motd": "Lema: con dos puntos = y un igual",
}


def _create(client: TestClient, **overrides: object) -> dict:
    response = client.post("/api/v1/servers", json={**BASE_PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["server"]


def _root(folder: str) -> Path:
    return get_settings().servers_dir / folder


def test_crear_genera_la_estructura_completa(client: TestClient) -> None:
    server = _create(client)
    root = _root(server["folder"])

    assert (root / "eula.txt").is_file()
    assert (root / "server.properties").is_file()
    assert (root / "ops.json").is_file()
    assert (root / "whitelist.json").is_file()
    assert (root / "logs").is_dir()
    assert (root / "world").is_dir()
    assert (root / "plugins").is_dir()  # paper admite plugins
    assert not (root / "mods").exists()

    assert "eula=true" in (root / "eula.txt").read_text(encoding="utf-8")
    assert json.loads((root / "ops.json").read_text(encoding="utf-8")) == []


def test_forge_crea_mods_y_no_plugins() -> None:
    # Forge aún no se crea por la API (su descarga llega en la fase 8), pero el
    # instalador de disco ya debe saber montar su estructura.
    from app.models import Difficulty, GameMode, Server, ServerStatus, ServerType
    from app.services.server_installer import ServerInstaller

    fs = ServerFilesystem(get_settings().servers_dir)
    server = Server(
        name="Con Mods",
        folder="con-mods",
        type=ServerType.FORGE,
        version="1.20.1",
        status=ServerStatus.STOPPED,
        port=25581,
        difficulty=Difficulty.NORMAL,
        gamemode=GameMode.SURVIVAL,
    )
    try:
        root = ServerInstaller(fs).install(server)
        assert (root / "mods").is_dir()
        assert not (root / "plugins").exists()
    finally:
        fs.remove("con-mods", missing_ok=True)


def test_properties_reflejan_la_configuracion(client: TestClient) -> None:
    server = _create(client, hardcore=True, seed="semilla123", whitelist_enabled=True)
    content = (_root(server["folder"]) / "server.properties").read_text(encoding="utf-8")

    assert "server-port=25580" in content
    assert "motd=Lema\\: con dos puntos \\= y un igual" in content
    assert "hardcore=true" in content
    assert "difficulty=hard" in content  # hardcore fuerza dificultad
    assert "level-seed=semilla123" in content
    assert "white-list=true" in content


def test_actualizar_regenera_properties(client: TestClient) -> None:
    server = _create(client)
    response = client.patch(f"/api/v1/servers/{server['id']}", json={"motd": "Nuevo lema"})
    assert response.status_code == 200

    content = (_root(server["folder"]) / "server.properties").read_text(encoding="utf-8")
    assert "motd=Nuevo lema" in content


def test_eliminar_borra_la_carpeta(client: TestClient) -> None:
    server = _create(client)
    root = _root(server["folder"])
    assert root.exists()

    assert client.delete(f"/api/v1/servers/{server['id']}").status_code == 204
    assert not root.exists()


def test_carpeta_ocupada_en_disco_genera_sufijo(client: TestClient) -> None:
    ocupada = get_settings().servers_dir / "ocupada"
    ocupada.mkdir(parents=True, exist_ok=True)
    try:
        server = _create(client, name="Ocupada")
        assert server["folder"] == "ocupada-2"
    finally:
        fs = ServerFilesystem(get_settings().servers_dir)
        fs.remove("ocupada", missing_ok=True)
        fs.remove("ocupada-2", missing_ok=True)


def test_filesystem_bloquea_rutas_fuera_del_sandbox() -> None:
    fs = ServerFilesystem(get_settings().servers_dir)
    with pytest.raises(PathTraversalError):
        fs.path_of("../fuera")
    with pytest.raises(PathTraversalError):
        fs.write_file("cualquiera", "../../escape.txt", "x")


def test_escape_properties_value() -> None:
    assert escape_properties_value("a=b:c") == "a\\=b\\:c"
    assert escape_properties_value("ruta\\windows") == "ruta\\\\windows"
    assert escape_properties_value("salto\nde línea") == "salto\\nde línea"
    assert escape_properties_value("emoji ☺") == "emoji \\u263a"
