"""Pruebas de la integración con Tailscale.

El ejecutable se sustituye por respuestas grabadas del formato real de
``tailscale status --json``: se comprueba la lectura del estado y, sobre todo,
la distinción entre conexión directa y por relé, que es el dato que decide si
Tailscale mejora la latencia frente al túnel.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import tailscale_service

CLI = Path(r"C:\Program Files\Tailscale\tailscale.exe")

ESTADO_CONECTADO = {
    "BackendState": "Running",
    "Self": {"HostName": "AlePc", "TailscaleIPs": ["100.101.102.103"], "Online": True},
    "Peer": {
        "nodekey:aaa": {
            "HostName": "pc-de-juan",
            "TailscaleIPs": ["100.101.102.50"],
            "Online": True,
            "CurAddr": "190.1.2.3:41641",  # conexión directa
            "Relay": "",
            "OS": "windows",
        },
        "nodekey:bbb": {
            "HostName": "portatil-de-ana",
            "TailscaleIPs": ["100.101.102.60"],
            "Online": True,
            "CurAddr": "",  # sin dirección directa: va por relé
            "Relay": "mia",
            "OS": "windows",
        },
        "nodekey:ccc": {
            "HostName": "pc-apagado",
            "TailscaleIPs": ["100.101.102.70"],
            "Online": False,
            "CurAddr": "",
            "Relay": "nyc",
            "OS": "linux",
        },
    },
}


def _fake_cli(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr(tailscale_service, "find_cli", lambda: CLI)
    monkeypatch.setattr(
        tailscale_service,
        "_run",
        lambda cli, *args, timeout=20.0: subprocess.CompletedProcess(
            args=list(args), returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )


def test_sin_instalar_explica_que_lo_instala_la_app(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tailscale_service, "find_cli", lambda: None)

    body = client.get("/api/v1/tailscale").json()
    assert body["installed"] is False
    assert body["own_ip"] is None
    assert any("instala sola" in nota for nota in body["notes"])
    assert body["invite_url"].startswith("https://login.tailscale.com/admin")


def test_distingue_conexion_directa_de_rele(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli(monkeypatch, ESTADO_CONECTADO)

    body = client.get("/api/v1/tailscale").json()
    assert body["installed"] is True
    assert body["running"] is True
    assert body["own_ip"] == "100.101.102.103"

    por_nombre = {peer["name"]: peer for peer in body["peers"]}
    assert por_nombre["pc-de-juan"]["direct"] is True
    assert por_nombre["portatil-de-ana"]["direct"] is False
    assert por_nombre["portatil-de-ana"]["relay"] == "mia"

    # Los desconectados van al final de la lista.
    assert body["peers"][-1]["name"] == "pc-apagado"


def test_avisa_si_todo_va_por_rele(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    solo_rele = json.loads(json.dumps(ESTADO_CONECTADO))
    solo_rele["Peer"]["nodekey:aaa"]["CurAddr"] = ""
    solo_rele["Peer"]["nodekey:aaa"]["Relay"] = "mia"
    _fake_cli(monkeypatch, solo_rele)

    body = client.get("/api/v1/tailscale").json()
    assert any("por relé" in nota for nota in body["notes"])


def test_no_avisa_si_hay_alguna_directa(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli(monkeypatch, ESTADO_CONECTADO)
    body = client.get("/api/v1/tailscale").json()
    assert not any("por relé" in nota for nota in body["notes"])


def test_falta_iniciar_sesion(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_cli(
        monkeypatch,
        {"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/abc123"},
    )

    body = client.get("/api/v1/tailscale").json()
    assert body["needs_login"] is True
    assert body["running"] is False
    assert body["login_url"] == "https://login.tailscale.com/a/abc123"
    assert any("iniciar sesión" in nota for nota in body["notes"])


def test_salida_ilegible_no_rompe_la_interfaz(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tailscale_service, "find_cli", lambda: CLI)
    monkeypatch.setattr(
        tailscale_service,
        "_run",
        lambda cli, *args, timeout=20.0: subprocess.CompletedProcess(
            args=list(args), returncode=1, stdout="no soy json", stderr=""
        ),
    )

    body = client.get("/api/v1/tailscale").json()
    assert body["installed"] is True
    assert body["running"] is False
    assert any("no responde" in nota for nota in body["notes"])


def test_iniciar_sesion_sin_instalar_se_rechaza(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tailscale_service, "find_cli", lambda: None)
    response = client.post("/api/v1/tailscale/login")
    assert response.status_code == 422
    assert "no está instalado" in response.json()["message"]


def test_instalador_elegido_por_arquitectura(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tailscale_service,
        "get_json",
        lambda url: {
            "Version": "1.98.10",
            "MSIs": {"amd64": "tailscale-setup-1.98.10-amd64.msi", "arm64": "arm.msi"},
        },
    )
    monkeypatch.setattr(tailscale_service.platform, "machine", lambda: "AMD64")

    filename, url = tailscale_service.latest_installer()
    assert filename == "tailscale-setup-1.98.10-amd64.msi"
    assert url == f"{tailscale_service.PKGS_BASE}/{filename}"
