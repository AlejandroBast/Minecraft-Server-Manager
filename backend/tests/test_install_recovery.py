"""Recuperación de una instalación que no llegó a completarse.

Reproduce el caso real reportado tras clonar el repositorio: la descarga de
Java se corta (internet, antivirus o cierre de la aplicación), el servidor
queda sin ``java_path`` y al pulsar Iniciar aparecía un mensaje sin salida que
obligaba a borrarlo y crearlo de nuevo.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import session_scope
from app.models import Server
from app.models.enums import ServerStatus
from app.services import maintenance

PAYLOAD = {"name": "Interrumpido", "type": "paper", "version": "1.21.4", "port": 25601}


def _create_with_failed_install(client: TestClient) -> dict:
    """Servidor creado cuya instalación se quedó a medias."""
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    with session_scope() as session:
        row = session.get(Server, server["id"])
        row.status = ServerStatus.ERROR
        row.java_path = None
        row.jar_file = None
        row.last_error = "La descarga de Java se interrumpió."
    return server


def test_un_servidor_recien_creado_no_figura_como_instalado(client: TestClient) -> None:
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    assert server["installed"] is False  # la instalación corre en segundo plano


def test_iniciar_sin_instalar_explica_como_arreglarlo(client: TestClient) -> None:
    server = _create_with_failed_install(client)

    response = client.post(f"/api/v1/servers/{server['id']}/start")
    assert response.status_code == 422

    mensaje = response.json()["message"]
    assert "Reintentar instalación" in mensaje  # dice qué hacer, no «recrea el servidor»
    assert response.json()["details"]["reason"] == "not_installed"


def test_reintentar_instalacion_recupera_el_servidor(client: TestClient) -> None:
    server = _create_with_failed_install(client)
    assert client.get(f"/api/v1/servers/{server['id']}").json()["installed"] is False

    response = client.post(f"/api/v1/servers/{server['id']}/install/retry")
    assert response.status_code == 202

    # El sustituto de la instalación (conftest) la completa al instante.
    recuperado = client.get(f"/api/v1/servers/{server['id']}").json()
    assert recuperado["status"] == "stopped"
    assert recuperado["last_error"] is None


def test_no_se_reinstala_lo_que_ya_esta_instalando(client: TestClient) -> None:
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    with session_scope() as session:
        session.get(Server, server["id"]).status = ServerStatus.INSTALLING

    response = client.post(f"/api/v1/servers/{server['id']}/install/retry")
    assert response.status_code == 409


def test_cierre_inesperado_durante_la_instalacion(client: TestClient) -> None:
    """El caso que más se da: cerrar la aplicación mientras descarga."""
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    with session_scope() as session:
        row = session.get(Server, server["id"])
        row.status = ServerStatus.INSTALLING
        row.java_path = None

    maintenance.recover_state()  # lo que ocurre al volver a arrancar

    quedo = client.get(f"/api/v1/servers/{server['id']}").json()
    assert quedo["status"] == "error"
    assert quedo["installed"] is False
    assert "a medias" in quedo["last_error"]

    # Y desde ahí se puede recuperar sin borrar nada.
    assert client.post(f"/api/v1/servers/{server['id']}/install/retry").status_code == 202
    assert client.get(f"/api/v1/servers/{server['id']}").json()["status"] == "stopped"
