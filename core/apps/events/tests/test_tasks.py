"""Testes unitários para tasks Celery de eventos."""

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.tasks import process_alpr_detection_task
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestProcessAlprDetectionTask:
    """Testes da task Celery de processamento ALPR."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        self.tenant = TenantFactory()
        self.camera = CameraFactory(
            name="Cam Portaria",
            is_online=True,
            tenant=self.tenant,
        )
        self.payload = {
            "plate": "ABC1D23",
            "camera_id": self.camera.id,
            "confidence": 0.95,
            "timestamp": "2026-03-13T10:30:00+00:00",
            "image_url": "http://cam.local/snapshot.jpg",
        }

    @patch("apps.events.services.publish_event")
    def test_calls_process_alpr_detection(self, mock_publish):
        """Task chama o service com input correto."""
        # Act
        result = process_alpr_detection_task(self.payload)

        # Assert
        assert result is not None
        event = Event.objects.get(id=result)
        assert event.event_type == "alpr.detected"
        assert event.payload["plate"] == "ABC1D23"

    @patch("apps.events.services.publish_event")
    def test_returns_event_id_on_success(self, mock_publish):
        """Retorna ID do evento criado."""
        # Act
        result = process_alpr_detection_task(self.payload)

        # Assert
        assert isinstance(result, int)
        assert Event.objects.filter(id=result).exists()

    @patch("apps.events.services.publish_event")
    def test_handles_camera_not_found(self, mock_publish):
        """Retorna None quando câmera não existe."""
        # Arrange
        self.payload["camera_id"] = 99999

        # Act
        result = process_alpr_detection_task(self.payload)

        # Assert
        assert result is None
        assert Event.objects.count() == 0

    @patch("apps.events.services.publish_event")
    def test_handles_missing_optional_fields(self, mock_publish):
        """Processa payload sem campos opcionais."""
        # Arrange
        del self.payload["image_url"]

        # Act
        result = process_alpr_detection_task(self.payload)

        # Assert
        assert result is not None
        event = Event.objects.get(id=result)
        assert "image_url" not in event.payload
