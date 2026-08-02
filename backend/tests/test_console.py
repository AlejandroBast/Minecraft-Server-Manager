"""Pruebas del ciclo de vida del proceso y de la consola.

Usan ``fake_server.py`` como sustituto del java real: el gestor de procesos se
prueba con un subproceso de verdad (stdin, stdout, códigos de salida) sin
depender de un server.jar ni de Java.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.services.process_manager as pm
from app.core.config import get_settings

FAKE_SERVER = Path(__file__).parent / "fake_server.py"
BASE_PAYLOAD = {"name": "Consolero", "type": "paper", "version": "1.21.4", "port": 25590}

# Capturado antes de que la fixture lo sustituya, para los tests que necesitan
# la validación real del comando de arranque.
_REAL_BUILD_COMMAND = pm.ProcessManager._build_command


@pytest.fixture(autouse=True)
def java_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pm.ProcessManager,
        "_build_command",
        lambda self, server, jar_path: [sys.executable, "-u", str(FAKE_SERVER)],
    )


def _create_ready(client: TestClient) -> dict:
    """Crea un servidor y simula que su instalación terminó (jar + java)."""
    server = client.post("/api/v1/servers", json=BASE_PAYLOAD).json()["server"]
    root = get_settings().servers_dir / server["folder"]
    (root / "server.jar").write_bytes(b"jar de mentira")

    from app.db.session import session_scope
    from app.models import Server

    with session_scope() as session:
        row = session.get(Server, server["id"])
        row.jar_file = "server.jar"
        row.java_path = sys.executable
    return server


def _wait_status(client: TestClient, server_id: int, expected: str, timeout: float = 10) -> str:
    deadline = time.monotonic() + timeout
    status = ""
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/servers/{server_id}").json()["status"]
        if status == expected:
            return status
        time.sleep(0.1)
    return status


def test_ciclo_completo_arrancar_comando_detener(client: TestClient) -> None:
    server = _create_ready(client)
    server_id = server["id"]

    response = client.post(f"/api/v1/servers/{server_id}/start")
    assert response.status_code == 202
    assert _wait_status(client, server_id, "online") == "online"

    detail = client.get(f"/api/v1/servers/{server_id}").json()
    assert detail["uptime_seconds"] is not None and detail["uptime_seconds"] >= 0

    sent = client.post(f"/api/v1/servers/{server_id}/console", json={"command": "/say hola"})
    assert sent.status_code == 200
    assert sent.json()["sent"] == "say hola"  # la barra inicial se quita

    deadline = time.monotonic() + 5
    lines: list[str] = []
    while time.monotonic() < deadline:
        output = client.get(f"/api/v1/servers/{server_id}/console").json()
        lines = [item["line"] for item in output["lines"]]
        if any("ejecutado: say hola" in line for line in lines):
            break
        time.sleep(0.1)
    assert any("Done (0.123s)!" in line for line in lines)
    assert any("ejecutado: say hola" in line for line in lines)

    response = client.post(f"/api/v1/servers/{server_id}/stop")
    assert response.status_code == 202
    assert _wait_status(client, server_id, "stopped") == "stopped"


def test_no_se_puede_arrancar_dos_veces(client: TestClient) -> None:
    server = _create_ready(client)
    client.post(f"/api/v1/servers/{server['id']}/start")
    assert _wait_status(client, server["id"], "online") == "online"

    response = client.post(f"/api/v1/servers/{server['id']}/start")
    assert response.status_code == 409

    client.post(f"/api/v1/servers/{server['id']}/stop")
    _wait_status(client, server["id"], "stopped")


def test_arrancar_sin_jar_da_error_claro(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pm.ProcessManager, "_build_command", _REAL_BUILD_COMMAND)
    server = client.post(
        "/api/v1/servers", json={**BASE_PAYLOAD, "name": "Sin Jar", "port": 25591}
    ).json()["server"]

    from app.db.session import session_scope
    from app.models import Server

    with session_scope() as session:
        session.get(Server, server["id"]).java_path = sys.executable

    response = client.post(f"/api/v1/servers/{server['id']}/start")
    assert response.status_code == 422
    assert "server.jar" in response.json()["message"]


def test_comando_invalido_se_rechaza(client: TestClient) -> None:
    server = _create_ready(client)
    client.post(f"/api/v1/servers/{server['id']}/start")
    _wait_status(client, server["id"], "online")

    for invalido in ("", "   ", "a" * 501):
        response = client.post(
            f"/api/v1/servers/{server['id']}/console", json={"command": invalido}
        )
        assert response.status_code == 422, invalido

    client.post(f"/api/v1/servers/{server['id']}/stop")
    _wait_status(client, server["id"], "stopped")


def test_comando_con_servidor_parado_da_conflicto(client: TestClient) -> None:
    server = _create_ready(client)
    response = client.post(f"/api/v1/servers/{server['id']}/console", json={"command": "list"})
    assert response.status_code == 409
