"""analytics_service — FastAPI app com lifespan gerenciando o Orchestrator."""
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config.settings import settings
from core.django_client import close_session, get_rois  # noqa: F401 — pré-aquece importações
from core.mediamtx_connector import MediaMTXConnector
from core.orchestrator import Orchestrator
from core.plugin_loader import PluginLoader
from core.redis_bus import RedisBus
from routers import face_extract

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra o Orchestrator junto com a aplicação."""
    global _orchestrator

    bus = RedisBus()
    await bus.connect()

    loader = PluginLoader()
    plugins = await loader.load_all()

    if not plugins:
        logger.warning("Nenhum plugin carregado — serviço iniciado sem processamento")

    connector = MediaMTXConnector()
    _orchestrator = Orchestrator(connector=connector, bus=bus, plugins=plugins)
    await _orchestrator.start()

    logger.info(
        "analytics_service pronto: %d plugin(s) carregado(s)",
        len(plugins),
    )

    try:
        yield
    finally:
        logger.info("analytics_service encerrando")
        await _orchestrator.stop()
        await loader.shutdown_all()
        await bus.disconnect()
        await close_session()


app = FastAPI(
    title="VMS Analytics Service",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(face_extract.router)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check — retorna status do orchestrator."""
    if _orchestrator is None:
        return JSONResponse({"status": "starting"}, status_code=503)
    status = await _orchestrator.status()
    return JSONResponse({"status": "ok", **status})
