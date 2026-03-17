"""Testes para task de ALPR com normalização de fabricantes."""
from unittest.mock import patch

import pytest

from apps.events.tasks import process_vendor_alpr_task
from tests.factories import CameraFactory


@pytest.mark.unit
class TestProcessVendorAlprTask:
    """Testes do process_vendor_alpr_task."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        """Cria câmera para testes."""
        self.camera = CameraFactory(manufacturer="hikvision")

    def test_hikvision_normalizes_and_creates_event(self):
        """Payload Hikvision é normalizado e gera evento."""
        raw_payload = {
            "EventNotificationAlert": {
                "channelID": "1",
                "dateTime": "2026-03-13T10:30:00-03:00",
                "ANPR": {
                    "licensePlate": "ABC1D23",
                    "confidenceLevel": 95,
                    "pictureURL": "http://cam.local/snap.jpg",
                },
            },
        }

        with patch("apps.events.services.publish_event"):
            result = process_vendor_alpr_task(
                "hikvision", self.camera.id, raw_payload,
            )

        assert result is not None

    def test_intelbras_normalizes_and_creates_event(self):
        """Payload Intelbras é normalizado e gera evento."""
        raw_payload = {
            "PlateResult": {
                "plate_number": "XYZ-9A87",
                "confidence": 0.90,
                "capture_time": "2026-03-13 10:30:00",
                "channel": 1,
            },
        }

        with patch("apps.events.services.publish_event"):
            result = process_vendor_alpr_task(
                "intelbras", self.camera.id, raw_payload,
            )

        assert result is not None

    def test_generic_normalizes_and_creates_event(self):
        """Payload genérico é normalizado e gera evento."""
        raw_payload = {
            "plate": "DEF5G67",
            "confidence": 0.85,
            "timestamp": "2026-03-13T10:30:00Z",
        }

        with patch("apps.events.services.publish_event"):
            result = process_vendor_alpr_task(
                "generic", self.camera.id, raw_payload,
            )

        assert result is not None

    def test_unsupported_manufacturer_returns_none(self):
        """Fabricante não suportado retorna None."""
        result = process_vendor_alpr_task("samsung", self.camera.id, {})

        assert result is None

    def test_invalid_camera_returns_none(self):
        """Câmera inexistente retorna None."""
        raw_payload = {
            "plate": "ABC1234",
            "confidence": 0.8,
            "timestamp": "2026-03-13T10:30:00Z",
        }

        result = process_vendor_alpr_task("generic", 99999, raw_payload)

        assert result is None

    def test_duplicate_detection_returns_none(self):
        """Segunda detecção idêntica dentro do TTL retorna None (dedup)."""
        raw_payload = {
            "plate": "DUP1A23",
            "confidence": 0.9,
            "timestamp": "2026-03-13T10:30:00Z",
        }

        with patch("apps.events.services.publish_event"):
            first = process_vendor_alpr_task(
                "generic", self.camera.id, raw_payload,
            )
            second = process_vendor_alpr_task(
                "generic", self.camera.id, raw_payload,
            )

        assert first is not None
        assert second is None

    def test_invalid_payload_returns_none(self):
        """Payload inválido para o fabricante retorna None."""
        result = process_vendor_alpr_task(
            "hikvision", self.camera.id, {"bad": "data"},
        )

        assert result is None
