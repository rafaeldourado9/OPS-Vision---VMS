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
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='recording.start', durable=True)

            count = 0
            for cam in cameras:
                message = {
                    'camera_id': str(cam.id),
                    'tenant_id': str(cam.tenant_id),
                    'stream_url': cam.stream_url,
                }
                channel.basic_publish(
                    exchange='',
                    routing_key='recording.start',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                count += 1

            connection.close()
            self.stdout.write(self.style.SUCCESS(f'{count} mensagens recording.start publicadas.'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'RabbitMQ indisponível: {e}'))
