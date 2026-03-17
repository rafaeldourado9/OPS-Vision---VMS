"""Testes unitários para deduplicação ALPR via Redis."""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.events.models import Event
from apps.events.services import ALPRDetectionInput, process_alpr_detection
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestAlprDeduplication:
    """Testes de deduplicação ALPR por Redis SET + TTL."""

    def setup_method(self):
        """Setup executado antes de cada teste."""
        cache.clear()
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=True)
        self.timestamp = datetime(2026, 3, 13, 10, 30, 0, tzinfo=UTC)
        self.input = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=self.camera.id,
            confidence=0.95,
            timestamp=self.timestamp,
        )

    @patch("apps.events.services.publish_event")
    def test_first_detection_creates_event(self, mock_publish):
        """Primeira detecção de placa cria evento normalmente."""
        event = process_alpr_detection(self.input)

        assert event is not None
        assert Event.objects.count() == 1
        assert event.plate == "ABC1D23"

    @patch("apps.events.services.publish_event")
    def test_duplicate_within_ttl_returns_none(self, mock_publish):
        """Segunda detecção idêntica dentro do TTL é ignorada."""
        process_alpr_detection(self.input)
        result = process_alpr_detection(self.input)

        assert result is None
        assert Event.objects.count() == 1

    @patch("apps.events.services.publish_event")
    def test_duplicate_does_not_publish_event(self, mock_publish):
        """Duplicata não publica evento no event bus."""
        process_alpr_detection(self.input)
        mock_publish.reset_mock()

        process_alpr_detection(self.input)

        mock_publish.assert_not_called()

    @patch("apps.events.services.publish_event")
    def test_different_plate_same_camera_creates_event(self, mock_publish):
        """Placa diferente na mesma câmera gera evento."""
        process_alpr_detection(self.input)

        other_input = ALPRDetectionInput(
            plate="XYZ9K87",
            camera_id=self.camera.id,
            confidence=0.90,
            timestamp=self.timestamp,
        )
        event = process_alpr_detection(other_input)

        assert event is not None
        assert Event.objects.count() == 2

    @patch("apps.events.services.publish_event")
    def test_same_plate_different_camera_creates_event(self, mock_publish):
        """Mesma placa em câmera diferente gera evento."""
        process_alpr_detection(self.input)

        camera2 = CameraFactory(tenant=self.tenant, is_online=True)
        other_input = ALPRDetectionInput(
            plate="ABC1D23",
            camera_id=camera2.id,
            confidence=0.95,
            timestamp=self.timestamp,
        )
        event = process_alpr_detection(other_input)

        assert event is not None
        assert Event.objects.count() == 2

    @patch("apps.events.services.publish_event")
    def test_after_cache_expiry_creates_event(self, mock_publish):
        """Após expiração do cache, mesma placa gera novo evento."""
        process_alpr_detection(self.input)

        # Simula expiração limpando o cache
        cache.clear()

        event = process_alpr_detection(self.input)

        assert event is not None
        assert Event.objects.count() == 2

    @patch("apps.events.services.publish_event")
    def test_dedup_key_format(self, mock_publish):
        """Verifica que a key de dedup segue o formato correto."""
        process_alpr_detection(self.input)

        key = f"alpr:dedup:{self.camera.id}:ABC1D23"
        assert cache.get(key) is not None

    @patch("apps.events.services.publish_event")
    @patch("django.core.cache.cache.add", return_value=True)
    def test_dedup_uses_cache_add_for_atomicity(self, mock_add, mock_publish):
        """Usa cache.add() para garantir atomicidade (SET NX)."""
        process_alpr_detection(self.input)

        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] == f"alpr:dedup:{self.camera.id}:ABC1D23"
