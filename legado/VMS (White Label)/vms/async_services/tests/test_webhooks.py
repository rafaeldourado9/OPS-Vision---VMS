"""Testes para rotas de webhooks."""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
class TestALPRWebhook:
    """Testes do endpoint ALPR."""

    async def test_alpr_webhook_returns_accepted(self, async_client):
        """Webhook ALPR válido retorna accepted."""
        with patch("routers.webhooks.process_alpr_event"):
            response = await async_client.post(
                "/webhooks/alpr",
                json={
                    "plate": "ABC-1D23",
                    "camera_id": 1,
                    "confidence": 0.97,
                    "timestamp": "2026-03-13T10:30:00Z",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_alpr_webhook_rejects_invalid_payload(self, async_client):
        """Webhook ALPR com payload inválido retorna 422."""
        response = await async_client.post(
            "/webhooks/alpr",
            json={"plate": "ABC-1D23"},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestVendorALPRWebhook:
    """Testes do endpoint ALPR com normalização por fabricante."""

    async def test_vendor_alpr_hikvision_returns_accepted(self, async_client):
        """Webhook ALPR Hikvision retorna accepted."""
        with patch("routers.webhooks.process_vendor_alpr_event"):
            response = await async_client.post(
                "/webhooks/alpr/hikvision?camera_id=10",
                json={
                    "EventNotificationAlert": {
                        "channelID": "1",
                        "dateTime": "2026-03-13T10:30:00-03:00",
                        "ANPR": {
                            "licensePlate": "ABC1D23",
                            "confidenceLevel": 95,
                        },
                    },
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_vendor_alpr_intelbras_returns_accepted(self, async_client):
        """Webhook ALPR Intelbras retorna accepted."""
        with patch("routers.webhooks.process_vendor_alpr_event"):
            response = await async_client.post(
                "/webhooks/alpr/intelbras?camera_id=20",
                json={
                    "PlateResult": {
                        "plate_number": "XYZ-9A87",
                        "confidence": 0.92,
                        "capture_time": "2026-03-13 10:30:00",
                        "channel": 1,
                    },
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_vendor_alpr_without_camera_id_returns_error(self, async_client):
        """Webhook ALPR sem camera_id retorna erro."""
        response = await async_client.post(
            "/webhooks/alpr/hikvision",
            json={"EventNotificationAlert": {}},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "error"

    async def test_vendor_alpr_dispatches_to_processor(self, async_client):
        """Webhook ALPR despacha para processor com parâmetros corretos."""
        raw_payload = {"plate": "ABC1234", "confidence": 0.9}

        with patch("routers.webhooks.process_vendor_alpr_event") as mock:
            await async_client.post(
                "/webhooks/alpr/generic?camera_id=5",
                json=raw_payload,
            )

        mock.assert_called_once_with("generic", 5, raw_payload)


@pytest.mark.asyncio
class TestMediaMTXWebhook:
    """Testes dos endpoints MediaMTX."""

    async def test_on_ready_returns_accepted(self, async_client):
        """Webhook on_ready retorna accepted."""
        with patch("routers.webhooks.process_mediamtx_event"):
            response = await async_client.post(
                "/webhooks/mediamtx/on_ready",
                json={
                    "path": "tenant-1/cam-1",
                    "source_type": "rtspSource",
                    "source_id": "abc123",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_on_read_returns_accepted(self, async_client):
        """Webhook on_read retorna accepted."""
        with patch("routers.webhooks.process_mediamtx_event"):
            response = await async_client.post(
                "/webhooks/mediamtx/on_read",
                json={
                    "path": "tenant-1/cam-1",
                    "reader_type": "webrtcSession",
                    "reader_id": "def456",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_record_segment_returns_accepted(self, async_client):
        """Webhook record_segment retorna accepted e despacha evento offline."""
        with patch("routers.webhooks.process_mediamtx_event") as mock_process:
            response = await async_client.post(
                "/webhooks/mediamtx/record_segment",
                json={
                    "path": "tenant-1/cam-1",
                    "file_path": "/recordings/tenant-1/cam-1/2026-03-14_09-00-00.mp4",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        mock_process.assert_called_once()
