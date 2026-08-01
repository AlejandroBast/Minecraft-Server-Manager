"""Proceso que imita a un servidor de Minecraft para las pruebas.

Imprime el arranque, marca el «Done» que el gestor usa para detectar EN LÍNEA,
hace eco de los comandos y termina limpiamente al recibir ``stop``.
"""

from __future__ import annotations

import sys

print("[Server thread/INFO]: Starting minecraft server (fake)", flush=True)
print('[Server thread/INFO]: Done (0.123s)! For help, type "help"', flush=True)

for raw in sys.stdin:
    command = raw.strip()
    if command == "stop":
        print("[Server thread/INFO]: Stopping server", flush=True)
        break
    print(f"[Server thread/INFO]: ejecutado: {command}", flush=True)
