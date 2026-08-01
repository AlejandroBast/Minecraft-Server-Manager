"""Excepciones de dominio y sus manejadores HTTP.

Los servicios nunca lanzan ``HTTPException``: se mantienen independientes del
framework. La traducción a códigos HTTP ocurre aquí, en el borde de la API.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app")


class AppError(Exception):
    """Error de negocio conocido por la aplicación."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    """El recurso existe o su estado impide la operación."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(AppError):
    status_code = 422  # el nombre de la constante cambió entre versiones de Starlette
    code = "validation_error"


class PathTraversalError(AppError):
    """Intento de acceder fuera de los directorios permitidos."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "path_traversal"


class ServerStateError(ConflictError):
    """La operación no es válida para el estado actual del servidor."""

    code = "invalid_server_state"


class ExternalServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("%s: %s", exc.code, exc.message, extra={"details": exc.details})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "Ha ocurrido un error interno.",
                "details": {},
            },
        )
