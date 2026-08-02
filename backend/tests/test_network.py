"""Pruebas del diagnóstico de red, la detección de CGNAT y las guías DNS.

La red se sustituye por completo: las pruebas verifican la lógica de
diagnóstico, no la conexión real del equipo.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services import network_service, upnp

GATEWAY = upnp.Gateway(control_url="http://192.168.1.1/ctl", service_type=upnp.WAN_SERVICES[0])


@pytest.fixture(autouse=True)
def sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "_ip_cache", None)
    monkeypatch.setattr(network_service, "get_local_ip", lambda: "192.168.1.50")
    monkeypatch.setattr(upnp, "discover_gateway", lambda timeout=3.0: None)


def _con_router(
    monkeypatch: pytest.MonkeyPatch, external_ip: str | None, mapped: bool = False
) -> None:
    monkeypatch.setattr(upnp, "discover_gateway", lambda timeout=3.0: GATEWAY)
    monkeypatch.setattr(upnp, "get_external_ip", lambda gateway: external_ip)
    monkeypatch.setattr(upnp, "has_port_mapping", lambda gateway, port, protocol="TCP": mapped)
    monkeypatch.setattr(network_service.upnp, "discover_gateway", lambda timeout=3.0: GATEWAY)
    monkeypatch.setattr(network_service.upnp, "get_external_ip", lambda gateway: external_ip)
    monkeypatch.setattr(
        network_service.upnp, "has_port_mapping", lambda gateway, port, protocol="TCP": mapped
    )


def test_ip_publica_ignora_las_fuentes_caidas(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_text(url: str) -> str:
        if url == network_service.PUBLIC_IP_SOURCES[0]:
            raise RuntimeError("caída")
        return " 203.0.113.9 \n"

    monkeypatch.setattr(network_service, "get_text", fake_get_text)
    assert network_service.get_public_ip(force=True) == "203.0.113.9"


def test_ips_discrepantes_delatan_cgnat(monkeypatch: pytest.MonkeyPatch) -> None:
    # Caso real observado: cada servicio ve una IP distinta del mismo rango.
    vistas = iter(["8.242.190.169", "8.242.190.164", "8.242.190.171"])
    monkeypatch.setattr(network_service, "get_text", lambda url: next(vistas))

    resultado = network_service.diagnose([25565])
    assert resultado.behind_carrier_nat is True
    assert any("pool de salida" in nota for nota in resultado.notes)
    assert any("túnel" in nota for nota in resultado.notes)


def test_respuesta_no_valida_no_se_acepta_como_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "<html>error</html>")
    assert network_service.get_public_ip(force=True) is None


def test_cgnat_detectado_por_ip_privada_en_el_router(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "203.0.113.9")
    _con_router(monkeypatch, external_ip="100.80.4.7")  # rango CGNAT

    resultado = network_service.diagnose([25565])
    assert resultado.behind_carrier_nat is True
    assert any("CGNAT" in nota for nota in resultado.notes)


def test_cgnat_detectado_por_discrepancia_de_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "8.242.190.169")
    _con_router(monkeypatch, external_ip="8.242.190.164")

    resultado = network_service.diagnose([25565])
    assert resultado.behind_carrier_nat is True
    assert any("otro NAT por medio" in nota for nota in resultado.notes)


def test_conexion_directa_no_marca_cgnat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "203.0.113.9")
    _con_router(monkeypatch, external_ip="203.0.113.9", mapped=True)

    resultado = network_service.diagnose([25565])
    assert resultado.behind_carrier_nat is False
    assert resultado.upnp_available is True
    assert resultado.ports[0].upnp_mapped is True
    assert resultado.notes == []


def test_sin_upnp_se_explica_como_hacerlo_a_mano(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "203.0.113.9")
    resultado = network_service.diagnose([25565])

    assert resultado.upnp_available is False
    assert any("redirección de puertos" in nota for nota in resultado.notes)

    exito, mensaje = network_service.open_port(25565)
    assert exito is False
    assert "192.168.1.50" in mensaje  # dice hacia qué IP redirigir


def test_instrucciones_dns() -> None:
    registros = network_service.dns_instructions("mc.midominio.com", "203.0.113.9", 25565)
    assert len(registros) == 1  # el puerto por defecto no necesita SRV
    assert registros[0].type == "A"
    assert registros[0].value == "203.0.113.9"

    con_srv = network_service.dns_instructions("MC.MiDominio.com", "203.0.113.9", 25570)
    assert [record.type for record in con_srv] == ["A", "SRV"]
    assert con_srv[1].name == "_minecraft._tcp.mc.midominio.com"
    assert con_srv[1].value == "0 5 25570 mc.midominio.com"


def test_endpoints_de_red(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_service, "get_text", lambda url: "203.0.113.9")

    response = client.get("/api/v1/network")
    assert response.status_code == 200
    assert response.json()["local_ip"] == "192.168.1.50"

    response = client.post("/api/v1/network/dns", json={"domain": "mc.ejemplo.com", "port": 25570})
    assert response.status_code == 200
    assert len(response.json()["records"]) == 2

    # Dominio con caracteres no válidos.
    assert client.post("/api/v1/network/dns", json={"domain": "mal dominio"}).status_code == 422
