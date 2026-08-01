"""Pruebas de los endpoints de sistema y preferencias."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.system_info import _parse_java_major


def test_system_info(client: TestClient) -> None:
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    body = response.json()

    assert body["os"] in {"Windows", "Linux", "Darwin"}
    assert body["cpu"]["physical_cores"] >= 1
    assert body["memory"]["total_mb"] > 0
    assert body["disk"]["free_gb"] >= 0
    assert body["network"]["local_ip"]
    assert isinstance(body["java"]["installed"], bool)


def test_recomendaciones_para_todos_los_tipos(client: TestClient) -> None:
    response = client.get("/api/v1/system/recommendations")
    assert response.status_code == 200
    body = response.json()
    assert {item["server_type"] for item in body} == {
        "vanilla", "paper", "purpur", "spigot", "fabric", "forge", "neoforge",
    }
    for item in body:
        assert item["memory_min_mb"] <= item["memory_max_mb"]


def test_parse_java_major() -> None:
    assert _parse_java_major("1.8.0_491") == 8
    assert _parse_java_major("17.0.9") == 17
    assert _parse_java_major("21") == 21
    assert _parse_java_major("desconocido") is None


def test_leer_y_actualizar_preferencias(client: TestClient) -> None:
    original = client.get("/api/v1/settings").json()["values"]
    assert original["language"] == "es"

    response = client.put("/api/v1/settings", json={"values": {"theme": "light"}})
    assert response.status_code == 200
    assert response.json()["values"]["theme"] == "light"

    client.put("/api/v1/settings", json={"values": {"theme": original["theme"]}})


def test_preferencias_rechazan_claves_desconocidas(client: TestClient) -> None:
    response = client.put("/api/v1/settings", json={"values": {"cualquier_cosa": "1"}})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_preferencias_exigen_ruta_absoluta(client: TestClient) -> None:
    response = client.put("/api/v1/settings", json={"values": {"servers_dir": "../fuera"}})
    assert response.status_code == 422
