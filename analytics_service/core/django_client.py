"""Cliente HTTP assíncrono para comunicação com o Django (VMS Platform)."""
import asyncio
import logging
import time
from typing import Any

import aiohttp

from analytics.base import AnalyticsResult, ROIConfig
from config.settings import settings

logger = logging.getLogger(__name__)

_BASE_URL = settings.DJANGO_INTERNAL_URL
_API_KEY = settings.ANALYTICS_SERVICE_API_KEY
_AUTH_HEADER = f"Analytics {_API_KEY}"

# Cache em memória: camera_id → (timestamp, list[ROIConfig])
_roi_cache: dict[int, tuple[float, list[ROIConfig]]] = {}
_roi_cache_lock = asyncio.Lock()

# Sessão HTTP compartilhada — criada uma vez, reutilizada por todas as chamadas.
# Evita o overhead de TCP handshake por requisição e as "Broken pipe" do server.
_session: aiohttp.ClientSession | None = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    """Retorna sessão HTTP compartilhada, criando se necessário."""
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            connector = aiohttp.TCPConnector(
                limit=30,
                keepalive_timeout=10,   # curto — Django runserver não suporta keep-alive longo
                ssl=False,
                force_close=True,       # fecha a conexão após cada request (evita Broken pipe)
            )
            _session = aiohttp.ClientSession(
                connector=connector,
                headers={"Authorization": _AUTH_HEADER},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    return _session


async def close_session() -> None:
    """Fecha a sessão HTTP compartilhada (chamar no shutdown)."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def get_rois(camera_id: int) -> list[ROIConfig]:
    """Busca ROIs ativas de uma câmera com cache TTL de settings.ROI_CACHE_TTL segundos.

    Args:
        camera_id: ID da câmera no Django.

    Returns:
        Lista de ROIConfig ou [] se falha ou sem ROIs.
    """
    async with _roi_cache_lock:
        cached = _roi_cache.get(camera_id)
        if cached and (time.monotonic() - cached[0]) < settings.ROI_CACHE_TTL:
            return cached[1]

    try:
        session = await _get_session()
        async with session.get(
            f"{_BASE_URL}/api/v1/analytics/internal/rois/",
            params={"camera": camera_id},
        ) as resp:
            if resp.status != 200:
                logger.warning(
                    "get_rois: Django retornou %d para câmera %d",
                    resp.status,
                    camera_id,
                )
                return []
            data: list[dict[str, Any]] = await resp.json()
    except Exception as exc:
        logger.error("get_rois: erro ao chamar Django: %s", exc)
        return []

    rois = [
        ROIConfig(
            id=item["id"],
            name=item["name"],
            ia_type=item["ia_type"],
            polygon_points=item["polygon_points"],
            config=item.get("config") or {},
        )
        for item in data
    ]

    async with _roi_cache_lock:
        _roi_cache[camera_id] = (time.monotonic(), rois)

    return rois


async def post_ingest(result: AnalyticsResult) -> None:
    """Envia resultado analítico para o endpoint de ingest do Django.

    Args:
        result: AnalyticsResult produzido por um plugin.
    """
    body = {
        "plugin": result.plugin,
        "camera_id": result.camera_id,
        "tenant_id": result.tenant_id,
        "event_type": result.event_type,
        "payload": result.payload,
    }
    try:
        session = await _get_session()
        async with session.post(
            f"{_BASE_URL}/api/v1/analytics/ingest/",
            json=body,
        ) as resp:
            if resp.status not in (200, 201, 202):
                text = await resp.text()
                logger.warning(
                    "post_ingest: Django retornou %d: %s", resp.status, text[:200]
                )
    except Exception as exc:
        logger.error("post_ingest: erro ao chamar Django: %s", exc)
