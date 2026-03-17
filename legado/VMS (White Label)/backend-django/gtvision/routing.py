from django.urls import path
from apps.detections.consumers import NotificationConsumer

websocket_urlpatterns = [
    path('ws/notifications/<uuid:tenant_id>/', NotificationConsumer.as_asgi()),
]
