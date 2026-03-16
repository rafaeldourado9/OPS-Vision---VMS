"""Publicadores de eventos no RabbitMQ."""
from typing import Any

from shared.event_bus import publish_event


def publish_camera_event(event_type: str, payload: dict[str, Any]) -> None:
    """Publica evento de câmera no event bus.

    Args:
        event_type: Tipo do evento (ex: "camera.online").
        payload: Dados do evento.
    """
    publish_event(event_type, payload)


def publish_detection_event(event_type: str, payload: dict[str, Any]) -> None:
    """Publica evento de detecção no event bus.

    Wrapper para eventos de analytics/detecção (ALPR, intrusão, etc.).
    Futuramente pode incluir enriquecimento, filtragem ou batching
    específico de eventos de detecção.

    Args:
        event_type: Tipo do evento (ex: "detection.alpr").
        payload: Dados do evento.
    """
    publish_event(event_type, payload)
