import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group_name = f'notifications_{self.tenant_id}'
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def ai_event(self, event):
        """Recebe evento de IA e envia para WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'ai_event',
            'payload': event['payload']
        }))
