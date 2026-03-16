"""Consumers RabbitMQ para o app de notificações.

Estes consumers escutam os eventos disparados no barramento
e acionam as regras de notificação configuradas.
"""
import logging
from typing import Any

from shared.event_bus import subscribe

from .services import evaluate_notification_rules

logger = logging.getLogger(__name__)


def start_notification_consumers() -> None:
    """Inicia os consumers de notificação em background.

    Escuta wildcards `detection.*` e `camera.*` para avaliar
    quem deve ser notificado.
    """
    logger.info("Iniciando consumers de notificação...")

    # Escuta eventos de detecção (ex: detection.alpr, detection.facial)
    subscribe(
        event_type="detection.*",
        callback=_handle_event,
        queue_name="notifications.detection",
    )

    # Escuta eventos de câmeras (ex: camera.online, camera.offline)
    subscribe(
        event_type="camera.*",
        callback=_handle_event,
        queue_name="notifications.camera",
    )


def _handle_event(payload: dict[str, Any]) -> None:
    """Processa um evento recebido e avalia as regras.

    O payload deve conter `tenant_id` e `event_type` para que
    o matching seja feito corretamente.
    """
    tenant_id = payload.get("tenant_id")
    event_type = payload.get("event_type")

    # Alguns eventos antigos podem não enviar o `event_type` explícito no payload,
    # caso precisássemos deduzir pelo routing key do RabbitMQ seria diferente,
    # mas o VMS atual injeta o type no payload.
    if not tenant_id or not event_type:
        logger.debug("Ignorando evento mal formatado para notificações: %s", payload)
        return

    logger.debug("Avaliando notificações para %s (tenant %d)", event_type, tenant_id)
    evaluate_notification_rules(
        event_type=event_type,
        tenant_id=tenant_id,
        payload=payload,
    )
