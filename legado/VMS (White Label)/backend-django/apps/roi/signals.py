import json
import os

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import RegionOfInterest


def _publish_roi_updated(camera):
    """Publish roi.updated to RabbitMQ for a given camera."""
    try:
        import pika

        rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        channel = connection.channel()
        channel.queue_declare(queue='roi.updated', durable=True)

        rois = list(RegionOfInterest.objects.filter(
            camera=camera, active=True
        ).values('id', 'name', 'polygon', 'ia_type', 'ia_types', 'config'))

        from apps.cameras.models import DetectionMask
        masks = list(DetectionMask.objects.filter(
            camera=camera, active=True
        ).values('id', 'name', 'polygon'))

        mediamtx_url = f'rtsp://mediamtx:8554/live/{camera.tenant_id}/{camera.id}'

        message = {
            'camera_id': str(camera.id),
            'tenant_id': str(camera.tenant_id),
            'stream_url': mediamtx_url,
            'roi_list': rois,
            'masks': masks,
        }

        channel.basic_publish(
            exchange='',
            routing_key='roi.updated',
            body=json.dumps(message, default=str),
        )
        connection.close()
    except Exception as e:
        print(f'[ROI Signal] Erro ao publicar roi.updated: {e}')


@receiver(post_save, sender=RegionOfInterest)
def roi_post_save(sender, instance, **kwargs):
    _publish_roi_updated(instance.camera)


@receiver(post_delete, sender=RegionOfInterest)
def roi_post_delete(sender, instance, **kwargs):
    _publish_roi_updated(instance.camera)
