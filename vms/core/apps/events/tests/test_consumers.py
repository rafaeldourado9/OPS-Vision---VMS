"""Testes para consumidores RabbitMQ de eventos de câmera."""
from unittest.mock import patch

import pytest

from apps.events.consumers import _handle_camera_event
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestHandleCameraEvent:
    """Testes do handler de eventos de câmera."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=False)

    @patch("apps.events.consumers.set_camera_online")
    def test_camera_online_event_calls_service(self, mock_set_online):
        """Evento camera.online chama set_camera_online(True)."""
        payload = {
            "event_type": "camera.online",
            "camera_id": self.camera.id,
            "tenant_id": self.tenant.id,
        }

        _handle_camera_event(payload)

        mock_set_online.assert_called_once_with(self.camera.id, is_online=True)

    @patch("apps.events.consumers.set_camera_online")
    def test_camera_offline_event_calls_service(self, mock_set_online):
        """Evento camera.offline chama set_camera_online(False)."""
        payload = {
            "event_type": "camera.offline",
            "camera_id": self.camera.id,
            "tenant_id": self.tenant.id,
        }

        _handle_camera_event(payload)

        mock_set_online.assert_called_once_with(self.camera.id, is_online=False)

    @patch("apps.events.consumers.set_camera_online")
    def test_unknown_event_type_is_ignored(self, mock_set_online):
        """Eventos desconhecidos (camera.created, etc.) não chamam set_camera_online."""
        payload = {
            "event_type": "camera.created",
            "camera_id": self.camera.id,
            "tenant_id": self.tenant.id,
        }

        _handle_camera_event(payload)

        mock_set_online.assert_not_called()

    @patch("apps.events.consumers.set_camera_online")
    def test_missing_camera_id_is_ignored(self, mock_set_online):
        """Payload sem camera_id não propaga exceção."""
        payload = {"event_type": "camera.online"}

        _handle_camera_event(payload)  # Não deve explodir

        mock_set_online.assert_not_called()

    @patch("apps.events.consumers.set_camera_online")
    def test_camera_not_found_does_not_crash(self, mock_set_online):
        """Camera inexistente não propaga exceção para o consumer."""
        from apps.cameras.models import Camera

        mock_set_online.side_effect = Camera.DoesNotExist

        payload = {
            "event_type": "camera.online",
            "camera_id": 99999,
            "tenant_id": self.tenant.id,
        }

        _handle_camera_event(payload)  # Deve absorver o erro
