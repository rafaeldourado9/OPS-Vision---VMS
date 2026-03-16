import pytest

from apps.events.serializers import EventSerializer
from tests.factories import EventFactory


@pytest.mark.django_db
class TestEventSerializer:
    def test_serialize_event(self):
        """Valida que o evento é serializado corretamente com todos os campos."""
        event = EventFactory()
        serializer = EventSerializer(event)

        data = serializer.data

        assert data["id"] == event.id
        assert data["event_type"] == event.event_type
        assert data["payload"] == event.payload
        assert data["camera_id"] == event.camera_id
        assert data["camera_name"] == event.camera.name
        assert data["plate"] == event.plate
        assert data["confidence"] == event.confidence
        assert "occurred_at" in data

    def test_read_only_fields(self):
        """Valida que campos derivados como camera_name são read_only."""
        event = EventFactory()
        serializer = EventSerializer(event)

        metadata = serializer.get_fields()

        assert metadata["camera_name"].read_only is True
        assert metadata["id"].read_only is True
        assert metadata["occurred_at"].read_only is True
