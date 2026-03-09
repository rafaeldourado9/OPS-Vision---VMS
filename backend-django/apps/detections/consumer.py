import asyncio
import os
import json
import pika
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from apps.detections.models import AIEvent


RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')


class EventConsumer:
    def __init__(self):
        self.channel_layer = get_channel_layer()

    @sync_to_async
    def save_event(self, event_data):
        """Persiste evento no banco"""
        return AIEvent.objects.create(
            tenant_id=event_data['tenant_id'],
            camera_id=event_data['camera_id'],
            roi_id=event_data['roi_id'],
            event_type=event_data['event_type'],
            snapshot_path=event_data['snapshot_path'],
            event_data=event_data['data'],
            detected_at=event_data['detected_at']
        )

    async def notify_operators(self, event, tenant_id):
        """Notifica operadores via WebSocket"""
        await self.channel_layer.group_send(
            f'notifications_{tenant_id}',
            {
                'type': 'ai_event',
                'payload': {
                    'id': str(event.id),
                    'camera_id': str(event.camera_id),
                    'event_type': event.event_type,
                    'event_data': event.event_data,
                    'detected_at': event.detected_at.isoformat()
                }
            }
        )

    def consume(self):
        """Consome fila ai.events"""
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue='ai.events', durable=True)
        
        def callback(ch, method, properties, body):
            event_data = json.loads(body)
            
            # Salva no banco
            event = asyncio.run(self.save_event(event_data))
            
            # Notifica via WebSocket
            asyncio.run(self.notify_operators(event, event_data['tenant_id']))
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        channel.basic_consume(queue='ai.events', on_message_callback=callback)
        channel.start_consuming()


if __name__ == '__main__':
    consumer = EventConsumer()
    consumer.consume()
