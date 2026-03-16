"""Lógica de domínio para eventos."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.cameras.models import Camera
from shared.event_bus import publish_event

from .models import Event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ALPRDetectionInput:
    """Dados de uma detecção ALPR normalizada.

    Attributes:
        plate: Placa detectada.
        camera_id: ID interno da câmera.
        confidence: Confiança da detecção (0.0 a 1.0).
        timestamp: Data/hora da detecção.
        image_url: URL do snapshot (opcional).
    """

    plate: str
    camera_id: int
    confidence: float
    timestamp: datetime
    image_url: str | None = None


def create_event(
    event_type: str,
    tenant_id: int,
    camera_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Cria e persiste um evento no banco.

    Args:
        event_type: Tipo do evento.
        tenant_id: ID do tenant.
        camera_id: ID da câmera (opcional).
        payload: Dados adicionais do evento.

    Returns:
        Evento criado.
    """
    return Event.objects.create(
        event_type=event_type,
        tenant_id=tenant_id,
        camera_id=camera_id,
        payload=payload or {},
    )


def _is_alpr_duplicate(camera_id: int, plate: str) -> bool:
    """Verifica se detecção ALPR é duplicada via Redis.

    Usa ``SET key value EX ttl NX`` para atomicidade.
    Se a key já existe, é duplicata dentro da janela TTL.

    Args:
        camera_id: ID da câmera.
        plate: Placa detectada.

    Returns:
        True se é duplicata (já existe no cache), False caso contrário.
    """
    ttl = settings.ALPR_DEDUP_TTL_SECONDS
    key = f"alpr:dedup:{camera_id}:{plate}"
    was_set = cache.add(key, "1", timeout=ttl)
    return not was_set


def process_alpr_detection(data: ALPRDetectionInput) -> Event | None:
    """Processa detecção ALPR: deduplica, persiste evento e publica no event bus.

    Busca a câmera para obter o tenant_id, verifica deduplicação via Redis
    (1 evento por placa por câmera dentro da janela TTL), cria um Event com
    tipo ``alpr.detected``, e publica ``detection.alpr`` para consumidores
    downstream (notificações, dashboards).

    Detecções com confiança abaixo de ``ALPR_LOW_CONFIDENCE_THRESHOLD``
    recebem a flag ``low_confidence=True`` no payload.

    Args:
        data: Dados normalizados da detecção.

    Returns:
        Evento criado, ou None se duplicata.

    Raises:
        Camera.DoesNotExist: Câmera não encontrada.
    """
    if _is_alpr_duplicate(data.camera_id, data.plate):
        logger.debug(
            "ALPR dedup: ignorando placa %s da câmera %d (duplicata)",
            data.plate,
            data.camera_id,
        )
        return None

    camera = Camera.objects.get(id=data.camera_id)

    threshold = settings.ALPR_LOW_CONFIDENCE_THRESHOLD
    is_low_confidence = data.confidence < threshold

    payload = _build_alpr_payload(data, is_low_confidence)

    event = Event.objects.create(
        event_type=Event.EventType.ALPR_DETECTED,
        camera_id=camera.id,
        tenant_id=camera.tenant_id,
        payload=payload,
        plate=data.plate,
        confidence=data.confidence,
    )

    publish_event("detection.alpr", {
        "event_id": event.id,
        "camera_id": camera.id,
        "tenant_id": camera.tenant_id,
        "plate": data.plate,
        "confidence": data.confidence,
        "low_confidence": is_low_confidence,
    })

    return event


def _build_alpr_payload(
    data: ALPRDetectionInput,
    is_low_confidence: bool,
) -> dict[str, Any]:
    """Constrói payload do evento ALPR.

    Args:
        data: Dados da detecção.
        is_low_confidence: Se a detecção é de baixa confiança.

    Returns:
        Payload para o Event.
    """
    payload: dict[str, Any] = {
        "plate": data.plate,
        "confidence": data.confidence,
        "timestamp": data.timestamp.isoformat(),
    }

    if is_low_confidence:
        payload["low_confidence"] = True

    if data.image_url is not None:
        payload["image_url"] = data.image_url

    return payload
