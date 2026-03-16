"""Consumidores RabbitMQ para eventos."""
import logging
from typing import Any

from apps.cameras.services import set_camera_online
from shared.event_bus import subscribe

logger = logging.getLogger(__name__)


def start_event_consumers() -> None:
    """Inicia consumidores de eventos do RabbitMQ."""
    subscribe(
        event_type="camera.*",
        callback=_handle_camera_event,
        queue_name="events.camera",
    )


def _handle_camera_event(payload: dict[str, Any]) -> None:
    """Processa eventos de câmera e atualiza status online/offline.

    Trata apenas camera.online e camera.offline.
    Outros tipos (camera.created, camera.updated, etc.) são ignorados.

    Args:
        payload: Dicionário com event_type, camera_id e tenant_id.
    """
    from apps.cameras.models import Camera

    event_type = payload.get("event_type")
    camera_id = payload.get("camera_id")

    if event_type not in ("camera.online", "camera.offline"):
        return

    if not camera_id:
        logger.warning("camera_event sem camera_id: %s", payload)
        return

    is_online = event_type == "camera.online"

    try:
        set_camera_online(camera_id, is_online=is_online)
        logger.info("Câmera %s marcada como %s", camera_id, "online" if is_online else "offline")
    except Camera.DoesNotExist:
        logger.error("Câmera %s não encontrada ao processar evento %s", camera_id, event_type)
