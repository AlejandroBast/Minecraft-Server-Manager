"""Lógica de negocio.

Los servicios no importan FastAPI ni conocen HTTP: reciben datos y una sesión,
devuelven modelos o lanzan excepciones de dominio. Esto permite reutilizarlos
desde WebSockets, tareas en segundo plano o una futura CLI.
"""
