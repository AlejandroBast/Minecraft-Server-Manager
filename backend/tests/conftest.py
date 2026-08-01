"""Configuración de pruebas.

Las variables de entorno se fijan antes de importar la aplicación para que
``Settings`` apunte a un directorio temporal: las pruebas nunca escriben en la
base de datos ni en los logs reales del usuario.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="msm-tests-"))
for _key, _sub in (
    ("MSM_SERVERS_DIR", "servers"),
    ("MSM_DOWNLOADS_DIR", "downloads"),
    ("MSM_JAVA_DIR", "downloads/java"),
    ("MSM_BACKUPS_DIR", "backups"),
    ("MSM_DATABASE_DIR", "database"),
    ("MSM_LOGS_DIR", "logs"),
    ("MSM_CONFIG_DIR", "config"),
    ("MSM_TEMP_DIR", "temp"),
):
    os.environ[_key] = str(_TMP_ROOT / _sub)

import shutil  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Server  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def sin_descargas_reales(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas nunca tocan la red: la instalación de fondo se simula.

    El sustituto marca el servidor como STOPPED, igual que haría la
    instalación real al terminar con éxito.
    """
    import app.api.v1.servers as servers_api
    from app.db.session import session_scope
    from app.models import Server, ServerStatus

    def instalacion_instantanea(server_id: int) -> None:
        with session_scope() as session:
            server = session.get(Server, server_id)
            if server is not None:
                server.status = ServerStatus.STOPPED

    monkeypatch.setattr(servers_api, "run_full_install", instalacion_instantanea)


@pytest.fixture(autouse=True)
def clean_servers(client: TestClient) -> None:
    """Cada prueba empieza sin servidores registrados ni carpetas en disco."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(Server.__table__.delete())

    servers_dir = get_settings().servers_dir
    if servers_dir.exists():
        for child in servers_dir.iterdir():
            shutil.rmtree(child, ignore_errors=True)

    backups_dir = get_settings().backups_dir
    if backups_dir.exists():
        for child in backups_dir.glob("*.zip"):
            child.unlink(missing_ok=True)
