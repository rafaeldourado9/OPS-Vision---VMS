"""Serializers para os eventos."""
from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    """Serializer para visualização de Eventos.

    Utilizado para listagem e detalhes na API de Event Query.
    """

    camera_name = serializers.CharField(source="camera.name", read_only=True)
    occurred_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "payload",
            "camera_id",
            "camera_name",
            "plate",
            "confidence",
            "occurred_at",
        ]
        read_only_fields = fields
