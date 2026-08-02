"""Server List Ping: consulta el estado de un servidor por su propio protocolo.

Es lo que hace el cliente de Minecraft para pintar la lista de servidores, así
que devuelve datos autoritativos (jugadores conectados, versión real, MOTD) en
cualquier tipo de servidor. Preferible a analizar el log, que cambia entre
versiones y entre Vanilla, Paper o Forge.

Referencia del protocolo: paquete de handshake (0x00) con «next state = 1»,
seguido de una petición de estado y una respuesta JSON.
"""

from __future__ import annotations

import json
import socket
import struct
import time
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger("servers")

PING_TIMEOUT = 2.0
PROTOCOL_UNKNOWN = -1  # el servidor responde igual y evita fingir una versión
MAX_RESPONSE_BYTES = 512 * 1024


@dataclass(frozen=True)
class ServerPing:
    online_players: int
    max_players: int
    version: str
    motd: str
    latency_ms: float


def _encode_varint(value: int) -> bytes:
    # Los VarInt del protocolo son enteros de 32 bits con signo: hay que pasar
    # a complemento a dos antes de desplazar. Sin esta máscara, un valor
    # negativo desplaza a la derecha indefinidamente (en Python los enteros no
    # tienen ancho fijo) y el bucle no termina nunca.
    value &= 0xFFFFFFFF
    data = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            data.append(byte | 0x80)
        else:
            data.append(byte)
            return bytes(data)


def _read_varint(sock: socket.socket) -> int:
    result = 0
    for shift in range(0, 35, 7):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("El servidor cerró la conexión.")
        result |= (chunk[0] & 0x7F) << shift
        if not chunk[0] & 0x80:
            return result
    raise ConnectionError("VarInt malformado en la respuesta.")


def _packet(packet_id: int, payload: bytes) -> bytes:
    body = _encode_varint(packet_id) + payload
    return _encode_varint(len(body)) + body


def _extract_motd(description: object) -> str:
    """El MOTD puede ser texto plano o un componente JSON con hijos."""
    if isinstance(description, str):
        return description
    if isinstance(description, dict):
        parts = [str(description.get("text", ""))]
        for extra in description.get("extra", []):
            parts.append(_extract_motd(extra))
        return "".join(parts)
    return ""


def ping(host: str, port: int, timeout: float = PING_TIMEOUT) -> ServerPing | None:
    """Consulta el servidor. ``None`` si no responde (apagado o arrancando)."""
    handshake = _packet(
        0x00,
        _encode_varint(PROTOCOL_UNKNOWN)
        + _encode_varint(len(host.encode()))
        + host.encode()
        + struct.pack(">H", port)
        + _encode_varint(1),
    )

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sent_at = time.monotonic()
            sock.sendall(handshake + _packet(0x00, b""))

            length = _read_varint(sock)
            if length <= 0 or length > MAX_RESPONSE_BYTES:
                return None
            _read_varint(sock)  # id del paquete de respuesta

            string_length = _read_varint(sock)
            buffer = bytearray()
            while len(buffer) < string_length:
                chunk = sock.recv(min(4096, string_length - len(buffer)))
                if not chunk:
                    break
                buffer.extend(chunk)
            latency = (time.monotonic() - sent_at) * 1000
    except (OSError, ConnectionError, struct.error) as error:
        logger.debug("Ping fallido a %s:%d: %s", host, port, error)
        return None

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None

    players = payload.get("players", {})
    return ServerPing(
        online_players=int(players.get("online", 0)),
        max_players=int(players.get("max", 0)),
        version=str(payload.get("version", {}).get("name", "")),
        motd=_extract_motd(payload.get("description", "")),
        latency_ms=round(latency, 1),
    )
