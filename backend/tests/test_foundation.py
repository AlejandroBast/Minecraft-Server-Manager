"""Pruebas de la base arquitectónica: sandbox de rutas, esquema y health."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app.core.exceptions import PathTraversalError, ValidationError
from app.core.paths import is_within, resolve_within, sanitize_folder_name
from app.db.base import Base
from app.main import app
from app.models import Backup, Server  # importar el paquete puebla Base.metadata


def test_resolve_within_permite_subrutas(tmp_path: Path) -> None:
    assert resolve_within(tmp_path, "world/region") == (tmp_path / "world" / "region").resolve()


@pytest.mark.parametrize("evil", ["../secreto", "..\\..\\Windows", "C:/Windows/System32"])
def test_resolve_within_bloquea_escapes(tmp_path: Path, evil: str) -> None:
    with pytest.raises(PathTraversalError):
        resolve_within(tmp_path, evil)


def test_is_within(tmp_path: Path) -> None:
    assert is_within(tmp_path, tmp_path / "servers" / "a")
    assert not is_within(tmp_path, tmp_path.parent)


def test_sanitize_folder_name() -> None:
    assert sanitize_folder_name("  Mi Servidor 1 ") == "Mi Servidor 1"
    for invalid in ("", "a", "con", "srv/../x", "nombre*ilegal"):
        with pytest.raises(ValidationError):
            sanitize_folder_name(invalid)


def test_tablas_registradas() -> None:
    assert {"servers", "backups", "configurations"} <= set(Base.metadata.tables)


def test_relaciones_resuelven() -> None:
    configure_mappers()
    assert Server.backups.property.mapper.class_ is Backup
    assert Backup.server.property.mapper.class_ is Server


def test_cors_admite_cualquier_puerto_de_localhost() -> None:
    """Si el 3000 está ocupado, la interfaz arranca en otro puerto y debe valer."""
    with TestClient(app) as client:
        for origen in ("http://localhost:3000", "http://localhost:50245", "http://127.0.0.1:8080"):
            response = client.get("/api/v1/health", headers={"Origin": origen})
            assert response.headers.get("access-control-allow-origin") == origen, origen

        # Un origen externo sigue sin estar permitido.
        response = client.get("/api/v1/health", headers={"Origin": "https://sitio-ajeno.com"})
        assert "access-control-allow-origin" not in response.headers


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
