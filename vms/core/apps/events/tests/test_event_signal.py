"""Testes para verificar que a criação de Event publica no Redis via signal."""
import pytest
from unittest.mock import patch

from apps.events.services import create_event, process_alpr_detection, ALPRDetectionInput
from tests.factories import CameraFactory, TenantFactory

from datetime import datetime, timezone


@pytest.mark.unit
@pytest.mark.django_db
class TestEventSignalPublishes:
    """Signal post_save em Event deve publicar no Redis pub/sub."""

    @patch("apps.events.signals.pubsub.publish")
    def test_create_event_triggers_publish(self, mock_publish):
        """create_event dispara o signal que publica no Redis."""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant)

        event = create_event(
            event_type="camera.online",
            tenant_id=tenant.id,
            camera_id=camera.id,
        )

        mock_publish.assert_called_once_with(
            "vms:realtime",
            {
                "type": "new_event",
                "event_id": event.id,
                "event_type": "camera.online",
                "camera_id": camera.id,
                "tenant_id": tenant.id,
            },
        )

    @patch("shared.event_bus.publish_event")
    @patch("apps.events.signals.pubsub.publish")
    def test_process_alpr_detection_triggers_publish(self, mock_publish, mock_bus):
        """process_alpr_detection também dispara o signal (via Event.objects.create)."""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant)

        event = process_alpr_detection(
            ALPRDetectionInput(
                plate="ABC-1234",
                camera_id=camera.id,
                confidence=0.95,
                timestamp=datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone.utc),
            )
        )

        # Signal deve ter sido chamado com new_event
        calls = mock_publish.call_args_list
        new_event_calls = [
            c for c in calls if c.args[1].get("type") == "new_event"
        ]
        assert len(new_event_calls) == 1
        assert new_event_calls[0].args[1]["event_id"] == event.id
        assert new_event_calls[0].args[1]["tenant_id"] == tenant.id

    @patch("shared.pubsub._get_client")
    def test_publish_failure_does_not_raise(self, mock_get_client):
        """Falha no Redis não propaga exceção — evento é criado normalmente."""
        mock_redis = mock_get_client.return_value
        mock_redis.publish.side_effect = Exception("redis down")

        tenant = TenantFactory()

        event = create_event(
            event_type="camera.online",
            tenant_id=tenant.id,
        )

        assert event.id is not None
