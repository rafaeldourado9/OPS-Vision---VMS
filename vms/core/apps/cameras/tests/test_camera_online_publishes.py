"""Testes para verificar que set_camera_online publica no Redis."""
import pytest
from unittest.mock import call, patch

from apps.cameras.services import set_camera_online
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestSetCameraOnlinePublishes:
    """set_camera_online deve publicar evento de status no pub/sub."""

    @patch("apps.cameras.services.pubsub.publish")
    def test_publishes_camera_online_event(self, mock_publish):
        """Publica evento camera_status com is_online=True."""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, is_online=False)

        set_camera_online(camera.id, is_online=True)

        mock_publish.assert_called_once_with(
            "vms:realtime",
            {
                "type": "camera_status",
                "camera_id": camera.id,
                "is_online": True,
                "tenant_id": tenant.id,
            },
        )

    @patch("apps.cameras.services.pubsub.publish")
    def test_publishes_camera_offline_event(self, mock_publish):
        """Publica evento camera_status com is_online=False."""
        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, is_online=True)

        set_camera_online(camera.id, is_online=False)

        mock_publish.assert_called_once_with(
            "vms:realtime",
            {
                "type": "camera_status",
                "camera_id": camera.id,
                "is_online": False,
                "tenant_id": tenant.id,
            },
        )

    @patch("shared.pubsub._get_client")
    def test_still_updates_db_even_if_publish_fails(self, mock_get_client):
        """Falha no Redis não impede a atualização do banco.

        pubsub.publish() captura exceções internamente — o serviço não deve propagar.
        """
        mock_redis = mock_get_client.return_value
        mock_redis.publish.side_effect = Exception("redis down")

        tenant = TenantFactory()
        camera = CameraFactory(tenant=tenant, is_online=False)

        set_camera_online(camera.id, is_online=True)

        camera.refresh_from_db()
        assert camera.is_online is True
