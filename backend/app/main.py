"""Fábrica de la aplicación FastAPI."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    config: Settings = app.state.settings
    config.ensure_directories()
    setup_logging(
        config.logs_dir,
        level=config.log_level,
        max_bytes=config.log_max_bytes,
        backup_count=config.log_backup_count,
    )
    logger = get_logger("app")

    from app.db.init_db import init_db

    init_db()

    # Tras un cierre inesperado quedan estados imposibles («en línea» sin
    # proceso) y restos de descargas: se corrigen antes de atender peticiones.
    from app.services.maintenance import cleanup, recover_state

    recover_state()
    cleanup(config)

    logger.info("%s v%s iniciado", config.app_name, config.app_version)
    yield
    # Al apagar la aplicación no pueden quedar procesos huérfanos.
    from app.services.process_manager import manager
    from app.services.tunnel_service import agent

    manager.stop_all()
    agent.stop()
    logger.info("%s detenido", config.app_name)


def create_app(config: Settings | None = None) -> FastAPI:
    config = config or settings
    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        # Se acepta cualquier puerto de localhost: si el 3000 está ocupado por
        # otro programa, Next arranca en otro y con una lista fija la interfaz
        # se quedaba sin backend mostrando un error engañoso. La API sólo
        # escucha en 127.0.0.1, así que no amplía el alcance real.
        allow_origin_regex=config.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=config.api_prefix)
    return app


app = create_app()
