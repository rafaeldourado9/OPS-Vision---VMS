"""Rotas de ingestão de webhooks."""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.webhook_processor import (
    process_alpr_event,
    process_mediamtx_event,
    process_vendor_alpr_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
limiter = Limiter(key_func=get_remote_address)


class ALPREvent(BaseModel):
    """Evento de reconhecimento de placa."""

    plate: str
    camera_id: int
    confidence: float
    timestamp: str
    image_url: str | None = None


class MediaMTXSourceEvent(BaseModel):
    """Evento de source do MediaMTX (on_ready, on_not_ready)."""

    path: str
    source_type: str
    source_id: str


class MediaMTXReaderEvent(BaseModel):
    """Evento de reader do MediaMTX (on_read, on_unread)."""

    path: str
    reader_type: str
    reader_id: str


@router.post("/alpr")
@limiter.limit("100/minute")
async def receive_alpr(
    request: Request,
    event: ALPREvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Recebe evento ALPR pré-normalizado e enfileira processamento."""
    background_tasks.add_task(process_alpr_event, event.model_dump())
    return {"status": "accepted"}


@router.post("/alpr/{manufacturer}")
@limiter.limit("100/minute")
async def receive_vendor_alpr(
    request: Request,
    manufacturer: str,
    background_tasks: BackgroundTasks,
    camera_id: int | None = None,
) -> dict[str, str]:
    """Recebe evento ALPR bruto de fabricante específico.

    O payload é enviado ao Celery para normalização e processamento.
    O ``manufacturer`` identifica o formato (hikvision, intelbras, generic).
    """
    if camera_id is None:
        return {"status": "error", "detail": "camera_id query parameter required"}

    raw_payload = await request.json()
    background_tasks.add_task(
        process_vendor_alpr_event, manufacturer, camera_id, raw_payload,
    )
    return {"status": "accepted"}


@router.post("/mediamtx/on_ready")
@limiter.limit("100/minute")
async def mediamtx_on_ready(
    request: Request,
    event: MediaMTXSourceEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Stream ficou disponível (câmera conectou)."""
    background_tasks.add_task(
        process_mediamtx_event, "on_ready", event.model_dump()
    )
    asyncio.create_task(_start_isapi_listener(event.path))
    return {"status": "accepted"}


@router.post("/mediamtx/on_not_ready")
@limiter.limit("100/minute")
async def mediamtx_on_not_ready(
    request: Request,
    event: MediaMTXSourceEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Stream ficou indisponível (câmera desconectou)."""
    background_tasks.add_task(
        process_mediamtx_event, "on_not_ready", event.model_dump()
    )
    asyncio.create_task(_stop_isapi_listener(event.path))
    return {"status": "accepted"}


async def _start_isapi_listener(path: str) -> None:
    """Busca URL RTSP no MediaMTX e inicia listener ISAPI."""
    try:
        from services.isapi_listener import isapi_manager
        from services.stream_manager import get_path_source

        source = await get_path_source(path)
        if not source:
            logger.warning("Sem source RTSP para %s, ISAPI não iniciado", path)
            return
        await isapi_manager.start_listener(path, source)
    except Exception:
        logger.exception("Erro ao iniciar ISAPI listener para %s", path)


async def _stop_isapi_listener(path: str) -> None:
    """Para o listener ISAPI de uma câmera."""
    try:
        from services.isapi_listener import isapi_manager

        await isapi_manager.stop_listener(path)
    except Exception:
        logger.exception("Erro ao parar ISAPI listener para %s", path)


@router.post("/mediamtx/on_read")
@limiter.limit("100/minute")
async def mediamtx_on_read(
    request: Request,
    event: MediaMTXReaderEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Alguém começou a assistir um stream."""
    background_tasks.add_task(
        process_mediamtx_event, "on_read", event.model_dump()
    )
    return {"status": "accepted"}


@router.post("/mediamtx/on_unread")
@limiter.limit("100/minute")
async def mediamtx_on_unread(
    request: Request,
    event: MediaMTXReaderEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Alguém parou de assistir um stream."""
    background_tasks.add_task(
        process_mediamtx_event, "on_unread", event.model_dump()
    )
    return {"status": "accepted"}


class MediaMTXRecordSegmentEvent(BaseModel):
    """Evento gerado quando um arquivo mp4 é fechado (segmento de gravação completo)."""
    
    path: str
    file_path: str


@router.post("/mediamtx/record_segment")
async def mediamtx_record_segment(
    event: MediaMTXRecordSegmentEvent,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Um arquivo mp4 foi finalizado e gravado no disco pelo MediaMTX."""
    background_tasks.add_task(
        process_mediamtx_event, "record_segment", event.model_dump()
    )
    return {"status": "accepted"}
