"""Testes para a task Celery cameras.set_online."""
from unittest.mock import patch

import pytest

from apps.cameras.tasks import set_camera_online_task
from tests.factories import CameraFactory, TenantFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestSetCameraOnlineTask:
    """Testes da task set_camera_online_task."""

    def setup_method(self):
        self.tenant = TenantFactory()
        self.camera = CameraFactory(tenant=self.tenant, is_online=False)

    @patch("apps.cameras.services.set_camera_online")
    def test_marks_camera_online(self, mock_set_online):
        """Task chama set_camera_online(camera_id, is_online=True)."""
        set_camera_online_task(self.camera.id, True)

        mock_set_online.assert_called_once_with(self.camera.id, is_online=True)

    @patch("apps.cameras.services.set_camera_online")
    def test_marks_camera_offline(self, mock_set_online):
        """Task chama set_camera_online(camera_id, is_online=False)."""
        set_camera_online_task(self.camera.id, False)

        mock_set_online.assert_called_once_with(self.camera.id, is_online=False)

    @patch("apps.cameras.services.set_camera_online")
    def test_camera_not_found_does_not_raise(self, mock_set_online):
        """Camera inexistente não propaga exceção — log de warning suficiente."""
        from apps.cameras.models import Camera

        mock_set_online.side_effect = Camera.DoesNotExist

        set_camera_online_task(99999, True)  # Não deve explodir
