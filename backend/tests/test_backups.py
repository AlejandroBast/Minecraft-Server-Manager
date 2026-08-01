"""Pruebas de copias de seguridad: crear, restaurar, zip-slip y borrado."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.core.config import get_settings

BASE_PAYLOAD = {"name": "Respaldado", "type": "paper", "version": "1.21.4", "port": 25595}


def _create_with_world(client: TestClient) -> dict:
    server = client.post("/api/v1/servers", json=BASE_PAYLOAD).json()["server"]
    root = get_settings().servers_dir / server["folder"]
    (root / "world" / "region").mkdir(parents=True, exist_ok=True)
    (root / "world" / "level.dat").write_bytes(b"datos del mundo")
    (root / "world" / "region" / "r.0.0.mca").write_bytes(b"chunk" * 100)
    (root / "session.lock").write_bytes(b"lock")
    return server


def _run_backup(client: TestClient, server_id: int, notes: str | None = None) -> dict:
    response = client.post(f"/api/v1/servers/{server_id}/backups", json={"notes": notes})
    assert response.status_code == 202, response.text
    backup_id = response.json()["id"]
    listado = client.get(f"/api/v1/servers/{server_id}/backups").json()
    return next(item for item in listado if item["id"] == backup_id)


def test_crear_backup_genera_zip_completo(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"], notes="antes del evento")

    assert backup["status"] == "completed"
    assert backup["size_bytes"] > 0
    assert backup["notes"] == "antes del evento"

    archive = get_settings().backups_dir / backup["file"]
    assert archive.is_file()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    assert "world/level.dat" in names
    assert "world/region/r.0.0.mca" in names
    assert "server.properties" in names
    assert "session.lock" not in names  # excluido a propósito


def test_restaurar_recupera_ficheros_borrados(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"])

    root = get_settings().servers_dir / server["folder"]
    (root / "world" / "level.dat").unlink()
    (root / "intruso.txt").write_text("no estaba en la copia", encoding="utf-8")

    response = client.post(f"/api/v1/backups/{backup['id']}/restore")
    assert response.status_code == 200, response.text

    assert (root / "world" / "level.dat").read_bytes() == b"datos del mundo"
    assert not (root / "intruso.txt").exists()  # la restauración reemplaza, no mezcla


def test_zip_slip_se_rechaza(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"])

    # Se corrompe la copia con una entrada que escapa de la carpeta.
    malicioso = io.BytesIO()
    with zipfile.ZipFile(malicioso, "w") as bundle:
        bundle.writestr("../../fuera.txt", "escape")
    archive = get_settings().backups_dir / backup["file"]
    archive.write_bytes(malicioso.getvalue())

    response = client.post(f"/api/v1/backups/{backup['id']}/restore")
    assert response.status_code == 422
    assert "rutas fuera" in response.json()["message"]

    escaped = get_settings().backups_dir.parent / "fuera.txt"
    assert not escaped.exists()
    # La carpeta original sigue intacta tras el intento fallido.
    assert (get_settings().servers_dir / server["folder"] / "world" / "level.dat").exists()


def test_eliminar_backup_borra_fichero_y_fila(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"])
    archive = get_settings().backups_dir / backup["file"]
    assert archive.exists()

    assert client.delete(f"/api/v1/backups/{backup['id']}").status_code == 204
    assert not archive.exists()
    assert client.get(f"/api/v1/servers/{server['id']}/backups").json() == []


def test_backup_de_servidor_inexistente_da_404(client: TestClient) -> None:
    assert client.post("/api/v1/servers/9999/backups", json={}).status_code == 404


def test_restaurar_copia_fallida_se_rechaza(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"])

    from app.db.session import session_scope
    from app.models import Backup
    from app.models.enums import BackupStatus

    with session_scope() as session:
        row = session.get(Backup, backup["id"])
        row.status = BackupStatus.FAILED

    response = client.post(f"/api/v1/backups/{backup['id']}/restore")
    assert response.status_code == 422


def test_backups_se_borran_en_cascada_con_el_servidor(client: TestClient) -> None:
    server = _create_with_world(client)
    backup = _run_backup(client, server["id"])
    assert client.delete(f"/api/v1/servers/{server['id']}").status_code == 204

    # La fila cae por la FK ON DELETE CASCADE; el zip huérfano permanece (se
    # limpia en la fase 10 con las tareas de mantenimiento).
    assert client.post(f"/api/v1/backups/{backup['id']}/restore").status_code == 404
