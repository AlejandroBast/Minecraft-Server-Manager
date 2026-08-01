"""Generación de los ficheros de configuración de un servidor de Minecraft.

Funciones puras: reciben el modelo y devuelven texto. El formato de
``server.properties`` es el "properties" de Java: hay que escapar ``=``, ``:``
y las barras invertidas en los valores, y los caracteres fuera de latin-1 se
escriben como secuencias ``\\uXXXX``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.models.server import Server

_ESCAPES = {"\\": "\\\\", "=": "\\=", ":": "\\:", "#": "\\#", "!": "\\!", "\n": "\\n", "\t": "\\t"}


def escape_properties_value(value: str) -> str:
    """Escapa un valor según el formato properties de Java."""
    result: list[str] = []
    for char in value:
        if char in _ESCAPES:
            result.append(_ESCAPES[char])
        elif ord(char) > 0xFF:
            result.append(f"\\u{ord(char):04x}")
        else:
            result.append(char)
    return "".join(result)


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return escape_properties_value(str(value))


def render_server_properties(server: Server) -> str:
    """Contenido de ``server.properties`` a partir de la configuración guardada.

    La base de datos es la fuente de verdad: el usuario cambia ajustes en la
    interfaz y el fichero se regenera; nunca al revés.
    """
    values: dict[str, object] = {
        "server-port": server.port,
        "max-players": server.max_players,
        "motd": server.motd,
        "difficulty": server.difficulty.value,
        "gamemode": server.gamemode.value,
        "online-mode": server.online_mode,
        "hardcore": server.hardcore,
        "allow-cheats": server.allow_commands,
        "white-list": server.whitelist_enabled,
        "enforce-whitelist": server.whitelist_enabled,
        "level-seed": server.seed or "",
        "level-name": "world",
        "enable-command-block": server.allow_commands,
        "spawn-protection": 16,
        "view-distance": 10,
        "simulation-distance": 10,
        "sync-chunk-writes": True,
        "enable-status": True,
        "enable-query": False,
        "enable-rcon": False,
    }
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Generado por Minecraft Server Manager — no editar a mano:",
        "# los cambios se hacen desde la interfaz y este fichero se regenera.",
        f"# {generated}",
        *(f"{key}={_fmt(value)}" for key, value in sorted(values.items())),
    ]
    return "\n".join(lines) + "\n"


def render_eula(accepted_at: datetime | None = None) -> str:
    """Contenido de ``eula.txt`` con la EULA aceptada.

    El usuario acepta la EULA de Mojang al crear el servidor desde la
    aplicación; este fichero sólo materializa esa aceptación.
    """
    stamp = (accepted_at or datetime.now(UTC)).strftime("%a %b %d %H:%M:%S UTC %Y")
    return (
        "# Aceptada desde Minecraft Server Manager.\n"
        "# https://aka.ms/MinecraftEULA\n"
        f"# {stamp}\n"
        "eula=true\n"
    )


def render_empty_json_list() -> str:
    """Contenido inicial de ``ops.json`` y ``whitelist.json``."""
    return json.dumps([], indent=2) + "\n"
