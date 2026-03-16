import json
import httpx
import logging
import pika
import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

MEDIAMTX_API = "http://mediamtx:9997/v3"
MEDIAMTX_AUTH = ("mediamtx_api_user", "GtV!sionMed1aMTX$2025")
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')


def get_path_name(camera):
    return f"live/{camera.tenant_id}/{camera.id}"


def add_mediamtx_path(camera):
    path_name = get_path_name(camera)
    payload = {
        "source": camera.stream_url,
        "sourceOnDemand": False,
    }
    try:
        r = httpx.post(
            f"{MEDIAMTX_API}/config/paths/add/{path_name}",
            json=payload,
            auth=MEDIAMTX_AUTH,
            timeout=5,
        )
        if r.status_code in (200, 201):
            logger.info(f"MediaMTX path added: {path_name}")
        else:
            logger.warning(f"MediaMTX add path failed ({r.status_code}): {r.text}")
    except Exception as e:
        logger.warning(f"MediaMTX unreachable on add: {e}")


def remove_mediamtx_path(camera):
    path_name = get_path_name(camera)
    try:
        r = httpx.delete(
            f"{MEDIAMTX_API}/config/paths/delete/{path_name}",
            auth=MEDIAMTX_AUTH,
            timeout=5,
        )
        if r.status_code in (200, 204):
            logger.info(f"MediaMTX path removed: {path_name}")
        else:
            logger.warning(f"MediaMTX delete path failed ({r.status_code}): {r.text}")
    except Exception as e:
        logger.warning(f"MediaMTX unreachable on delete: {e}")


def publish_rabbitmq(queue_name, message: dict):
    """Publica mensagem no RabbitMQ (síncrono, fire-and-forget)"""
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        logger.info(f"Published to {queue_name}: {message}")
    except Exception as e:
        logger.warning(f"RabbitMQ publish failed ({queue_name}): {e}")


@receiver(post_save, sender='cameras.Camera')
def camera_post_save(sender, instance, created, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields).issubset({'online', 'last_seen'}):
        return

    if instance.stream_protocol == 'rtsp' and instance.stream_url:
        add_mediamtx_path(instance)
        
        # Use MediaMTX URL instead of direct camera URL
        mediamtx_url = f'rtsp://mediamtx:8554/{get_path_name(instance)}'
        
        publish_rabbitmq('recording.start', {
            'camera_id': str(instance.id),
            'tenant_id': str(instance.tenant_id),
            'stream_url': mediamtx_url,
        })
        # Ativa frame grabber (captura thumbnails mesmo sem ROIs)
        publish_rabbitmq('camera.activated', {
            'camera_id': str(instance.id),
            'tenant_id': str(instance.tenant_id),
            'stream_url': mediamtx_url,
        })


@receiver(post_delete, sender='cameras.Camera')
def camera_post_delete(sender, instance, **kwargs):
    remove_mediamtx_path(instance)
    publish_rabbitmq('recording.stop', {
        'camera_id': str(instance.id),
    })
