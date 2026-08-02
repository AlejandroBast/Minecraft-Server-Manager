"""Pruebas del túnel de playit.gg.

La API externa y el proceso del agente se sustituyen: se comprueba la lógica y,
sobre todo, que la clave del agente nunca se filtre por la API.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.services import tunnel_service

CLAVE = "clave-de-agente-de-prueba-1234"

RESPUESTA_TUNELES = {
    "status": "success",
    "data": {
        "tunnels": [
            {
                "name": "Mi servidor",
                "active": True,
                "alloc": {
                    "data": {"assigned_domain": "ejemplo.gl.joinmc.link", "port_start": 25565}
                },
                "origin": {"data": {"local_port": 25565}},
            },
            {"name": "sin asignar", "alloc": {"data": {}}, "origin": {"data": {}}},
        ]
    },
}


@pytest.fixture(autouse=True)
def sin_playit(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Ni red ni proceso: la clave válida es una sola, cualquier otra falla.

    La clave vive en la tabla de configuración, que no se limpia entre pruebas:
    hay que borrarla aquí o una prueba arrastraría la de la anterior.
    """
    client.delete("/api/v1/tunnel/secret")

    def fake_api(secret: str, path: str) -> object:
        if secret != CLAVE:
            raise ValidationError(
                "La clave del agente no es válida. Cópiala de nuevo desde playit.gg."
            )
        return RESPUESTA_TUNELES

    monkeypatch.setattr(tunnel_service, "_api", fake_api)
    monkeypatch.setattr(tunnel_service.agent, "start", lambda secret, settings=None: None)
    monkeypatch.setattr(tunnel_service.agent, "stop", lambda: None)
    monkeypatch.setattr(tunnel_service.agent, "is_running", lambda: False)


def test_estado_inicial_explica_que_falta_la_clave(client: TestClient) -> None:
    body = client.get("/api/v1/tunnel").json()
    assert body["secret_configured"] is False
    assert body["running"] is False
    assert body["setup_url"].startswith("https://playit.gg/")
    assert any("clave de agente" in nota for nota in body["notes"])


def test_clave_invalida_se_rechaza_y_no_se_guarda(client: TestClient) -> None:
    response = client.put("/api/v1/tunnel/secret", json={"secret": "clave-que-no-vale"})
    assert response.status_code == 422
    assert client.get("/api/v1/tunnel").json()["secret_configured"] is False


def test_guardar_clave_y_ver_la_direccion(client: TestClient) -> None:
    response = client.put("/api/v1/tunnel/secret", json={"secret": CLAVE})
    assert response.status_code == 200

    body = response.json()
    assert body["secret_configured"] is True
    assert len(body["addresses"]) == 1  # el túnel sin dirección asignada se omite
    assert body["addresses"][0]["address"] == "ejemplo.gl.joinmc.link"
    assert body["addresses"][0]["port"] == 25565


def test_la_clave_nunca_sale_por_la_api(client: TestClient) -> None:
    client.put("/api/v1/tunnel/secret", json={"secret": CLAVE})

    # Ni en el estado del túnel...
    assert CLAVE not in client.get("/api/v1/tunnel").text
    # ...ni en las preferencias, aunque comparta tabla con ellas.
    ajustes = client.get("/api/v1/settings")
    assert CLAVE not in ajustes.text
    assert "playit_secret" not in ajustes.json()["values"]


def test_arrancar_sin_clave_se_rechaza(client: TestClient) -> None:
    response = client.post("/api/v1/tunnel/start")
    assert response.status_code == 422
    assert "clave del agente" in response.json()["message"]


def test_eliminar_la_clave(client: TestClient) -> None:
    client.put("/api/v1/tunnel/secret", json={"secret": CLAVE})
    assert client.delete("/api/v1/tunnel/secret").status_code == 204
    assert client.get("/api/v1/tunnel").json()["secret_configured"] is False


def test_binario_del_agente_fijado_por_hash() -> None:
    """Un ejecutable descargado debe verificarse, no basta con la URL."""
    filename, sha256 = tunnel_service.AGENT_BUILDS["Windows"]
    assert filename.endswith(".exe")
    assert len(sha256) == 64  # sha256 real del binario firmado v1.0.10
