"""Pruebas de estadísticas, ping de Minecraft y mantenimiento."""

from __future__ import annotations

import json
import socket
import struct
import threading

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import session_scope
from app.models import Backup, Server
from app.models.enums import BackupStatus, ServerStatus
from app.services import maintenance
from app.services.minecraft_ping import _encode_varint, _extract_motd, ping

PAYLOAD = {"name": "Medido", "type": "paper", "version": "1.21.4", "port": 25598}


def _fake_minecraft_server(response: dict) -> tuple[int, threading.Thread]:
    """Servidor TCP que responde un Server List Ping válido."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve() -> None:
        with listener:
            connection, _ = listener.accept()
            with connection:
                connection.recv(4096)  # handshake + petición de estado
                body = json.dumps(response).encode()
                packet = _encode_varint(0x00) + _encode_varint(len(body)) + body
                connection.sendall(_encode_varint(len(packet)) + packet)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return port, thread


def test_ping_lee_jugadores_y_version() -> None:
    port, thread = _fake_minecraft_server(
        {
            "players": {"online": 3, "max": 20},
            "version": {"name": "Paper 1.21.4"},
            "description": {"text": "Hola ", "extra": [{"text": "mundo"}]},
        }
    )
    resultado = ping("127.0.0.1", port)
    thread.join(timeout=2)

    assert resultado is not None
    assert resultado.online_players == 3
    assert resultado.max_players == 20
    assert resultado.version == "Paper 1.21.4"
    assert resultado.motd == "Hola mundo"


def test_ping_a_puerto_cerrado_devuelve_none() -> None:
    # Puerto reservado por el sistema pero sin nadie escuchando.
    assert ping("127.0.0.1", 1, timeout=0.5) is None


def test_extract_motd_admite_texto_y_componentes() -> None:
    assert _extract_motd("simple") == "simple"
    assert _extract_motd({"text": "a", "extra": [{"text": "b"}, "c"]}) == "abc"
    assert _extract_motd(None) == ""


def test_varint() -> None:
    assert _encode_varint(0) == b"\x00"
    assert _encode_varint(127) == b"\x7f"
    assert _encode_varint(128) == b"\x80\x01"
    assert _encode_varint(25565) == b"\xdd\xc7\x01"
    # -1 es el «protocolo desconocido» del handshake: sin la máscara de 32 bits
    # el codificador entraría en un bucle infinito.
    assert _encode_varint(-1) == b"\xff\xff\xff\xff\x0f"
    assert struct.unpack(">H", struct.pack(">H", 25565))[0] == 25565


def test_cpu_se_mide_reutilizando_el_proceso() -> None:
    """psutil sólo da CPU real si se reutiliza el mismo objeto Process."""
    import os

    from app.services.stats_service import _process_usage, _tracked_process

    primero = _tracked_process(os.getpid())
    segundo = _tracked_process(os.getpid())
    assert primero is segundo  # se reutiliza, no se recrea

    # Trabajo real para que haya algo que medir entre lecturas.
    _process_usage(os.getpid())
    total = 0
    for i in range(2_000_000):
        total += i
    cpu, memoria = _process_usage(os.getpid())  # type: ignore[misc]
    assert cpu > 0, "la CPU debería reflejar el trabajo hecho entre lecturas"
    assert memoria > 0


def test_stats_de_servidor_parado(client: TestClient) -> None:
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    response = client.get(f"/api/v1/servers/{server['id']}/stats")
    assert response.status_code == 200

    body = response.json()
    assert body["running"] is False
    assert body["cpu_percent"] is None
    assert body["online_players"] is None
    assert body["world_size_bytes"] > 0  # los ficheros de configuración ya ocupan
    assert body["disk_free_gb"] > 0


def test_recuperacion_de_estado_tras_cierre_inesperado(client: TestClient) -> None:
    online = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    instalando = client.post(
        "/api/v1/servers", json={**PAYLOAD, "name": "A Medias", "port": 25599}
    ).json()["server"]

    with session_scope() as session:
        session.get(Server, online["id"]).status = ServerStatus.ONLINE
        session.get(Server, instalando["id"]).status = ServerStatus.INSTALLING
        session.add(
            Backup(server_id=online["id"], file="x.zip", status=BackupStatus.RUNNING)
        )

    corregidos = maintenance.recover_state()
    assert corregidos == 3

    assert client.get(f"/api/v1/servers/{online['id']}").json()["status"] == "stopped"
    interrumpido = client.get(f"/api/v1/servers/{instalando['id']}").json()
    assert interrumpido["status"] == "error"
    assert "a medias" in interrumpido["last_error"]

    copias = client.get(f"/api/v1/servers/{online['id']}/backups").json()
    assert copias[0]["status"] == "failed"


def test_cleanup_borra_huerfanos_y_temporales(client: TestClient) -> None:
    settings = get_settings()
    settings.backups_dir.mkdir(parents=True, exist_ok=True)

    huerfano = settings.backups_dir / "servidor-borrado-20260101-000000.zip"
    huerfano.write_bytes(b"contenido huerfano")
    temporal = settings.backups_dir / "descarga-cortada.part"
    temporal.write_bytes(b"a medias")

    # Una copia registrada en la base de datos no debe tocarse.
    server = client.post("/api/v1/servers", json=PAYLOAD).json()["server"]
    legitima = settings.backups_dir / "legitima.zip"
    legitima.write_bytes(b"copia buena")
    with session_scope() as session:
        session.add(
            Backup(
                server_id=server["id"],
                file="legitima.zip",
                status=BackupStatus.COMPLETED,
                size_bytes=11,
            )
        )

    resultado = client.post("/api/v1/system/cleanup").json()

    assert resultado["orphan_backups_removed"] == 1
    assert resultado["bytes_freed"] == 18
    assert resultado["temp_files_removed"] == 1
    assert not huerfano.exists()
    assert not temporal.exists()
    assert legitima.exists()  # la registrada sobrevive
