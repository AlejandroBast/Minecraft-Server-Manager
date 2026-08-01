"""Pruebas del CRUD de servidores y de sus reglas de negocio."""

from __future__ import annotations

from fastapi.testclient import TestClient

BASE_PAYLOAD = {
    "name": "Mi Servidor",
    "type": "paper",
    "version": "1.21.4",
    "port": 25565,
    "max_players": 20,
    "motd": "Bienvenido",
}


def _create(client: TestClient, **overrides: object) -> dict:
    response = client.post("/api/v1/servers", json={**BASE_PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_crear_y_listar(client: TestClient) -> None:
    created = _create(client)
    server = created["server"]

    assert server["id"] > 0
    assert server["name"] == "Mi Servidor"
    assert server["folder"] == "mi-servidor"
    assert server["status"] == "installing"  # la descarga corre en segundo plano
    assert server["supports_plugins"] is True
    assert server["supports_mods"] is False

    listed = client.get("/api/v1/servers")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [server["id"]]


def test_nombre_duplicado_devuelve_409(client: TestClient) -> None:
    _create(client)
    response = client.post(
        "/api/v1/servers", json={**BASE_PAYLOAD, "name": "mi servidor", "port": 25570}
    )
    assert response.status_code == 409
    assert response.json()["error"] == "conflict"


def test_puerto_duplicado_devuelve_409(client: TestClient) -> None:
    _create(client)
    response = client.post("/api/v1/servers", json={**BASE_PAYLOAD, "name": "Otro"})
    assert response.status_code == 409


def test_carpetas_unicas_con_nombres_parecidos(client: TestClient) -> None:
    primero = _create(client, name="Mi Servidor")["server"]
    segundo = _create(client, name="mi-servidor", port=25570)["server"]
    assert primero["folder"] == "mi-servidor"
    assert segundo["folder"] == "mi-servidor-2"


def test_hardcore_fuerza_dificultad_dificil(client: TestClient) -> None:
    server = _create(client, hardcore=True, difficulty="easy")["server"]
    assert server["difficulty"] == "hard"


def test_validaciones_de_formato(client: TestClient) -> None:
    casos = [
        {"port": 80},
        {"port": 70000},
        {"max_players": 0},
        {"version": "1.21 4"},
        {"memory_min_mb": 4096, "memory_max_mb": 2048},
        {"name": "X"},
    ]
    for caso in casos:
        response = client.post("/api/v1/servers", json={**BASE_PAYLOAD, **caso})
        assert response.status_code == 422, f"{caso} debería rechazarse: {response.text}"


def test_nombre_con_caracteres_ilegales(client: TestClient) -> None:
    response = client.post("/api/v1/servers", json={**BASE_PAYLOAD, "name": "../../etc"})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_actualizar_servidor(client: TestClient) -> None:
    server = _create(client)["server"]
    response = client.patch(
        f"/api/v1/servers/{server['id']}", json={"motd": "Nuevo lema", "max_players": 40}
    )
    assert response.status_code == 200
    assert response.json()["motd"] == "Nuevo lema"
    assert response.json()["max_players"] == 40


def test_actualizar_rechaza_claves_desconocidas(client: TestClient) -> None:
    server = _create(client)["server"]
    response = client.patch(f"/api/v1/servers/{server['id']}", json={"status": "online"})
    assert response.status_code == 422


def test_servidor_inexistente(client: TestClient) -> None:
    assert client.get("/api/v1/servers/9999").status_code == 404
    assert client.delete("/api/v1/servers/9999").status_code == 404


def test_eliminar_servidor(client: TestClient) -> None:
    server = _create(client)["server"]
    assert client.delete(f"/api/v1/servers/{server['id']}").status_code == 204
    assert client.get(f"/api/v1/servers/{server['id']}").status_code == 404
