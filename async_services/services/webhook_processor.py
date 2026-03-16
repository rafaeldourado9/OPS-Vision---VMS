"""Processador de webhooks recebidos."""
import json
import logging
import os
from typing import Any

import pika
from celery import Celery

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
_celery_instance: Celery | None = None


def _get_celery_app() -> Celery:
    """Retorna instância Celery singleton conectada ao broker RabbitMQ."""
    global _celery_instance
    if _celery_instance is None:
        broker_url = (
            f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}"
            f"@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"
        )
        _celery_instance = Celery(broker=broker_url)
    return _celery_instance


def _parse_camera_id(mediamtx_path: str) -> int | None:
    """Extrai o camera_id do path no formato 'tenant-N/cam-M'.

    Args:
        mediamtx_path: Path como "tenant-3/cam-7".

    Returns:
        camera_id inteiro, ou None se o formato for inválido.
    """
    try:
        parts = mediamtx_path.split("/")
        if len(parts) == 2 and parts[1].startswith("cam-"):
            return int(parts[1].replace("cam-", ""))
    except (ValueError, IndexError):
        pass
    return None
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "vms")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "vmsdev")


def _get_rabbitmq_connection() -> pika.BlockingConnection:
    """Cria conexão com RabbitMQ com retry básico."""
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD),
            connection_attempts=3,
            retry_delay=2,
        )
    )


def _publish_to_rabbitmq(event_type: str, payload: dict[str, Any]) -> None:
    """Publica evento no RabbitMQ.

    Args:
        event_type: Routing key do evento.
        payload: Dados do evento.
    """
    try:
        connection = _get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(
            exchange="vms_events",
            exchange_type="topic",
            durable=True,
        )
        channel.basic_publish(
            exchange="vms_events",
            routing_key=event_type,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        connection.close()
    except Exception:
        logger.exception("Failed to publish event %s", event_type)
        raise


def process_alpr_event(payload: dict[str, Any]) -> None:
    """Processa evento ALPR pré-normalizado e despacha para Celery.

    Args:
        payload: Dados do evento ALPR (plate, camera_id, confidence, timestamp).
    """
    logger.info("ALPR event: plate=%s camera=%s confidence=%.2f",
                payload.get("plate"), payload.get("camera_id"),
                payload.get("confidence", 0))
    _get_celery_app().send_task(
        "events.process_alpr_detection",
        args=[payload],
        queue="analytics",
    )


def process_vendor_alpr_event(
    manufacturer: str,
    camera_id: int,
    raw_payload: dict[str, Any],
) -> None:
    """Processa evento ALPR bruto de fabricante específico.

    Despacha para Celery task que normaliza e processa.

    Args:
        manufacturer: Nome do fabricante (hikvision, intelbras, generic).
        camera_id: ID interno da câmera.
        raw_payload: Payload bruto do dispositivo.
    """
    logger.info(
        "Vendor ALPR event: manufacturer=%s camera_id=%d",
        manufacturer,
        camera_id,
    )
    _get_celery_app().send_task(
        "events.process_vendor_alpr",
        args=[manufacturer, camera_id, raw_payload],
        queue="analytics",
    )


def process_mediamtx_event(event_type: str, payload: dict[str, Any]) -> None:
    """Processa evento do MediaMTX.

    Eventos com ação imediata despachados como tasks Celery:
    - record_segment  → recordings.process_segment (indexa segmento no DB)
    - on_ready        → cameras.set_online(camera_id, True)
    - on_not_ready    → cameras.set_online(camera_id, False)

    Eventos informativos publicados no event bus (RabbitMQ):
    - on_read     → stream.viewer_joined
    - on_unread   → stream.viewer_left

    Args:
        event_type: Tipo do evento MediaMTX.
        payload: Dados do evento.
    """
    path = payload.get("path", "")
    logger.info("MediaMTX %s: path=%s", event_type, path)

    if event_type == "record_segment":
        file_path = payload.get("file_path")
        if path and file_path:
            _get_celery_app().send_task(
                "recordings.process_segment",
                args=[path, file_path],
                queue="default",
            )
        else:
            logger.warning("record_segment sem path/file_path: %s", payload)
        return

    if event_type in ("on_ready", "on_not_ready"):
        camera_id = _parse_camera_id(path)
        if camera_id is None:
            logger.warning("on_ready/on_not_ready com path inválido: %s", path)
            return
        is_online = event_type == "on_ready"
        _get_celery_app().send_task("cameras.set_online", args=[camera_id, is_online], queue="default")
        return

    # Eventos informativos → event bus
    event_map = {
        "on_read": "stream.viewer_joined",
        "on_unread": "stream.viewer_left",
    }
    routing_key = event_map.get(event_type, f"mediamtx.{event_type}")
    _publish_to_rabbitmq(routing_key, payload)


def process_isapi_event(
    path: str,
    internal_event_type: str,
    event_data: dict[str, str],
) -> None:
    """Processa evento ISAPI de uma câmera e despacha task Celery.

    Args:
        path: Path do MediaMTX (ex: tenant-1/cam-3).
        internal_event_type: Tipo interno (ex: motion.detected).
        event_data: Dados parseados do XML ISAPI.
    """
    camera_id = _parse_camera_id(path)
    if camera_id is None:
        logger.debug("ISAPI event com path inválido: %s", path)
        return

    logger.info(
        "ISAPI %s (%s) camera_id=%d state=%s",
        event_data.get("event_type"),
        internal_event_type,
        camera_id,
        event_data.get("event_state"),
    )

    _get_celery_app().send_task(
        "events.process_camera_event",
        args=[camera_id, internal_event_type, event_data],
        queue="default",
    )
