"""Comprobación de disponibilidad de puertos TCP en el equipo anfitrión."""

from __future__ import annotations

import socket

MIN_USER_PORT = 1024
MAX_PORT = 65535


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:  # noqa: S104
    """``True`` si ningún proceso escucha en ese puerto ahora mismo.

    Se comprueba en todas las interfaces porque así es como escuchará el
    servidor de Minecraft; el socket se cierra de inmediato y no acepta nada.

    No reserva el puerto: entre esta comprobación y el arranque del servidor
    podría ocuparlo otro proceso. Sirve para avisar, no para bloquear.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(start: int = 25565, attempts: int = 50) -> int | None:
    """Primer puerto libre a partir de ``start``; ``None`` si no encuentra."""
    for candidate in range(start, min(start + attempts, MAX_PORT + 1)):
        if is_port_free(candidate):
            return candidate
    return None
