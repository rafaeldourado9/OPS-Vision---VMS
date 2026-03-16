"""Testes unitários para services de eventos."""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.cameras.models import Camera
from apps.events.models import Event
from apps.events.services import ALPRDetectionInput, process_alpr_detection
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestProcessAlprDetection:
    """Testes do serviço de processamento de detecção ALPR."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        cache.clear()
        self.tenant = TenantFactory()
        self.camera = CameraFactory(
            name="Cam Portaria",
            location="Portaria",
            is_online=True,
            tenant=self.tenant,
        )
        self.timestamp = datetime(2026, 3, 13, 10, 30, 0, tzinfo=UTC)
        self.input = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.95,
            timestamp=self.timestamp,
            image_url="http://cam.local/snapshot.jpg",
        )

    @patch("apps.events.services.publish_event")
    def test_creates_event_in_database(self, mock_publish):
        """Cria evento no banco de dados."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert Event.objects.count() == 1
        assert event.id is not None
        assert event.event_type == Event.EventType.ALPR_DETECTED

    @patch("apps.events.services.publish_event")
    def test_event_type_is_alpr_detected(self, mock_publish):
        """Tipo do evento é alpr.detected."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert event.event_type == "alpr.detected"

    @patch("apps.events.services.publish_event")
    def test_event_linked_to_camera_and_tenant(self, mock_publish):
        """Evento associado à câmera e tenant corretos."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert event.camera_id == self.camera.id
        assert event.tenant_id == self.tenant.id

    @patch("apps.events.services.publish_event")
    def test_payload_contains_plate_and_confidence(self, mock_publish):
        """Payload contém placa, confiança e timestamp."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert event.payload["plate"] == "ABC1D23"
        assert event.payload["confidence"] == 0.95
        assert event.payload["timestamp"] == self.timestamp.isoformat()

    @patch("apps.events.services.publish_event")
    def test_low_confidence_flagged(self, mock_publish):
        """Detecção com baixa confiança recebe flag low_confidence."""
        # Arrange
        low_input = ALPRDetectionInput(
            plate="??X1?3?",
            camera_id=self.camera.id,
            confidence=0.30,
            timestamp=self.timestamp,
        )

        # Act
        event = process_alpr_detection(low_input)

        # Assert
        assert event.payload["low_confidence"] is True

    @patch("apps.events.services.publish_event")
    def test_high_confidence_not_flagged(self, mock_publish):
        """Detecção com alta confiança não tem flag low_confidence."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert "low_confidence" not in event.payload

    @patch("apps.events.services.publish_event")
    def test_low_confidence_uses_configurable_threshold(self, mock_publish):
        """Threshold de baixa confiança vem das settings."""
        # Arrange — confiança exatamente no limite
        edge_input = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.70,
            timestamp=self.timestamp,
        )

        # Act
        event = process_alpr_detection(edge_input)

        # Assert — 0.70 >= 0.70, portanto NÃO é low confidence
        assert "low_confidence" not in event.payload

    @patch("apps.events.services.publish_event")
    def test_publishes_detection_alpr_event(self, mock_publish):
        """Publica evento detection.alpr no event bus."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        mock_publish.assert_called_once_with(
            "detection.alpr",
            {
                "event_id": event.id,
                "camera_id": self.camera.id,
                "tenant_id": self.tenant.id,
                "plate": "ABC1D23",
                "confidence": 0.95,
                "low_confidence": False,
            },
        )

    @patch("apps.events.services.publish_event")
    def test_camera_not_found_raises_error(self, mock_publish):
        """Erro quando câmera não existe."""
        # Arrange
        invalid_input = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=99999,
            confidence=0.95,
            timestamp=self.timestamp,
        )

        # Act & Assert
        with pytest.raises(Camera.DoesNotExist):
            process_alpr_detection(invalid_input)

        # Assert — evento não deve ser publicado
        mock_publish.assert_not_called()

    @patch("apps.events.services.publish_event")
    def test_payload_includes_image_url_when_provided(self, mock_publish):
        """Payload inclui image_url quando fornecido."""
        # Act
        event = process_alpr_detection(self.input)

        # Assert
        assert event.payload["image_url"] == "http://cam.local/snapshot.jpg"

    @patch("apps.events.services.publish_event")
    def test_payload_excludes_image_url_when_none(self, mock_publish):
        """Payload não contém image_url quando não fornecido."""
        # Arrange
        input_no_image = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.95,
            timestamp=self.timestamp,
        )

        # Act
        event = process_alpr_detection(input_no_image)

        # Assert
        assert "image_url" not in event.payload
