"""
Publica recording.start no RabbitMQ para todas as câmeras RTSP ativas.
Executar no startup para garantir que gravações sejam iniciadas.
"""
import json
import pika
import os
import logging
from django.core.management.base import BaseCommand
from apps.cameras.models import Camera

logger = logging.getLogger(__name__)
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')


class Command(BaseCommand):
    help = 'Inicia gravações para todas as câmeras RTSP'

    def handle(self, *args, **options):
        cameras = Camera.objects.filter(stream_protocol='rtsp').exclude(stream_url='')
        if not cameras.exists():
            self.stdout.write('Nenhuma câmera RTSP encontrada.')
            return

        try:
            from apps.roi.models import RegionOfInterest
            
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='recording.start', durable=True)
            channel.queue_declare(queue='camera.activated', durable=True)
            channel.queue_declare(queue='roi.updated', durable=True)

            count = 0
            for cam in cameras:
                # Use MediaMTX URL instead of direct camera URL
                mediamtx_url = f'rtsp://mediamtx:8554/live/{cam.tenant_id}/{cam.id}'
                
                message = {
                    'camera_id': str(cam.id),
                    'tenant_id': str(cam.tenant_id),
                    'stream_url': mediamtx_url,
                }
                channel.basic_publish(
                    exchange='',
                    routing_key='recording.start',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                channel.basic_publish(
                    exchange='',
                    routing_key='camera.activated',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                
                # Publica roi.updated com as ROIs ativas da câmera
                rois = list(RegionOfInterest.objects.filter(
                    camera=cam, active=True
                ).values('id', 'name', 'polygon', 'ia_type', 'ia_types', 'config'))
                
                roi_message = {
                    'camera_id': str(cam.id),
                    'tenant_id': str(cam.tenant_id),
                    'stream_url': mediamtx_url,
                    'roi_list': rois,
                }
                channel.basic_publish(
                    exchange='',
                    routing_key='roi.updated',
                    body=json.dumps(roi_message, default=str),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                
                count += 1

            connection.close()
            self.stdout.write(self.style.SUCCESS(
                f'{count} câmeras: recording.start + camera.activated + roi.updated publicados.'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'RabbitMQ indisponível: {e}'))
