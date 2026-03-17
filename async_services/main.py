"""FastAPI — Serviços assíncronos do VMS."""
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from routers import health, sse, streaming, streaming_auth, webhooks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia startup/shutdown do app.

    No startup, restaura ISAPI listeners para câmeras já online
    no MediaMTX (ex: após restart do FastAPI).
    No shutdown, para todos os listeners.
    """
    from services.isapi_listener import isapi_manager
    from services.stream_manager import get_path_source, list_active_streams

    try:
        streams = await list_active_streams()
        for stream in streams:
            if stream["ready"]:
                path = stream["path"]
                source = await get_path_source(path)
                if source:
                    await isapi_manager.start_listener(path, source)
        logger.info(
            "ISAPI listeners restaurados: %d",
            len(isapi_manager.active_listeners),
        )
    except Exception:
        logger.exception("Falha ao restaurar ISAPI listeners no startup")

    yield

    await isapi_manager.stop_all()
    logger.info("ISAPI listeners encerrados")


limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="VMS Async Services",
    description="Serviços assíncronos para webhooks e controle de streams.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
_cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost,http://localhost:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(streaming.router)
app.include_router(streaming_auth.router)
app.include_router(sse.router)
