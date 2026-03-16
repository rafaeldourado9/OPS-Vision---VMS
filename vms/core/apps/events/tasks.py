"""Tarefas Celery para processamento de eventos."""
import logging
from datetime import datetime
from typing import Any

from celery import shared_task

from apps.cameras.models import Camera
from apps.events.normalizers import (
    UnsupportedManufacturerError,
    normalize_alpr_payload,
)
from apps.events.services import (
    ALPRDetectionInput,
    create_event,
    process_alpr_detection,
)

logger = logging.getLogger(__name__)


@shared_task(name="events.process_alpr_detection", queue="analytics")
def process_alpr_detection_task(
    payload: dict[str, Any],
) -> int | None:
    """Processa detecção ALPR recebida via RabbitMQ.

    Converte o payload serializado em ``ALPRDetectionInput``,
    chama o service de processamento e retorna o ID do evento
    criado.

    Args:
        payload: Dados da detecção (plate, camera_id, confidence,
                 timestamp, image_url).

    Returns:
        ID do evento criado, ou None se falhou.
    """
    try:
        data = ALPRDetectionInput(
            plate=payload["plate"],
            camera_id=payload["camera_id"],
            confidence=payload["confidence"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
            image_url=payload.get("image_url"),
        )

        event = process_alpr_detection(data)
        if event is None:
            logger.debug(
                "ALPR detection skipped (duplicate): plate=%s camera_id=%d",
                data.plate,
                data.camera_id,
            )
            return None

        logger.info(
            "ALPR detection processed: event_id=%d plate=%s camera_id=%d",
            event.id,
            data.plate,
            data.camera_id,
        )

        return event.id

    except Camera.DoesNotExist:
        logger.warning(
            "ALPR detection failed: camera_id=%s not found",
            payload.get("camera_id"),
        )
        return None

    except Exception:
        logger.exception(
            "ALPR detection failed: unexpected error for payload=%s",
            payload,
        )
        return None


@shared_task(name="events.process_vendor_alpr", queue="analytics")
def process_vendor_alpr_task(
    manufacturer: str,
    camera_id: int,
    raw_payload: dict[str, Any],
) -> int | None:
    """Normaliza payload ALPR de fabricante específico e processa.

    Recebe payload bruto do fabricante, normaliza via
    ``normalize_alpr_payload()`` e delega para
    ``process_alpr_detection()`` (dedup + persistência).

    Args:
        manufacturer: Nome do fabricante (hikvision, intelbras, generic).
        camera_id: ID interno da câmera.
        raw_payload: Payload bruto do dispositivo.

    Returns:
        ID do evento criado, ou None se duplicata/falha.
    """
    try:
        data = normalize_alpr_payload(manufacturer, camera_id, raw_payload)
        event = process_alpr_detection(data)
        if event is None:
            logger.debug(
                "Vendor ALPR skipped (duplicate): manufacturer=%s plate=%s",
                manufacturer,
                data.plate,
            )
            return None

        logger.info(
            "Vendor ALPR processed: manufacturer=%s event_id=%d plate=%s",
            manufacturer,
            event.id,
            data.plate,
        )
        return event.id

    except UnsupportedManufacturerError:
        logger.warning(
            "Vendor ALPR failed: unsupported manufacturer=%s",
            manufacturer,
        )
        return None

    except Camera.DoesNotExist:
        logger.warning(
            "Vendor ALPR failed: camera_id=%d not found",
            camera_id,
        )
        return None

    except Exception:
        logger.exception(
            "Vendor ALPR failed: manufacturer=%s camera_id=%d",
            manufacturer,
            camera_id,
        )
        return None


@shared_task(name="events.process_camera_event", queue="default")
def process_camera_event_task(
    camera_id: int,
    event_type: str,
    event_data: dict[str, Any],
) -> int | None:
    """Processa evento ISAPI de câmera (motion, videoloss, etc).

    Cria um Event no banco de dados. O signal post_save publica
    automaticamente no Redis para SSE em tempo real.

    Args:
        camera_id: ID da câmera.
        event_type: Tipo interno do evento (ex: motion.detected).
        event_data: Dados do evento ISAPI parseados.

    Returns:
        ID do evento criado, ou None se falhou.
    """
    try:
        camera = Camera.objects.get(id=camera_id)

        event = create_event(
            event_type=event_type,
            tenant_id=camera.tenant_id,
            camera_id=camera.id,
            payload={
                "source": "isapi",
                "isapi_event_type": event_data.get("event_type", ""),
                "event_state": event_data.get("event_state", ""),
                "channel_id": event_data.get("channel_id", ""),
                "ip_address": event_data.get("ip_address", ""),
                "date_time": event_data.get("date_time", ""),
            },
        )

        logger.info(
            "Camera event processed: event_id=%d type=%s camera_id=%d",
            event.id,
            event_type,
            camera_id,
        )
        return event.id

    except Camera.DoesNotExist:
        logger.warning(
            "Camera event failed: camera_id=%d not found", camera_id,
        )
        return None

    except Exception:
        logger.exception(
            "Camera event failed: camera_id=%d type=%s",
            camera_id, event_type,
        )
        return None
